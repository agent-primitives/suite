package agentsuite

import (
	"archive/tar"
	"compress/gzip"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"os"
	"path"
	"path/filepath"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/agent-primitives/suite/internal/contract"
)

const (
	maxContentEntries        = 100_000
	maxContentBytes          = int64(4 << 30)
	maxRetainedMetadataBytes = int64(256 << 20)
	maxPathBytes             = contract.MaxPathBytes
)

type contentEntry struct {
	Path       string
	Type       string
	Mode       uint32
	UID        int
	GID        int
	Size       int64
	Digest     string
	LinkTarget string
	Data       []byte
}

type contentSet struct {
	entries        map[string]contentEntry
	folded         map[string]string
	sourceType     string
	artifactDigest string
	declaredModes  map[string]uint32
}

func loadDirectory(root string) (*contentSet, error) {
	set := &contentSet{
		entries:    map[string]contentEntry{},
		folded:     map[string]string{},
		sourceType: "directory",
	}
	canonicalRoot, err := filepath.EvalSymlinks(root)
	if err != nil {
		return nil, err
	}
	rootHandle, err := os.OpenRoot(canonicalRoot)
	if err != nil {
		return nil, err
	}
	defer rootHandle.Close()
	rootFile, err := rootHandle.OpenFile(".", os.O_RDONLY|directoryReadFlags, 0)
	if err != nil {
		return nil, err
	}
	securityErr := checkDirectorySecurity(rootFile, true)
	closeErr := rootFile.Close()
	if err := errors.Join(securityErr, closeErr); err != nil {
		return nil, err
	}
	count := 0
	var total, retained int64
	err = fs.WalkDir(rootHandle.FS(), ".", func(current string, _ fs.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		if current == "." {
			return nil
		}
		count++
		if count > maxContentEntries {
			return fmt.Errorf("content has more than %d entries", maxContentEntries)
		}
		name, err := validateContentPath(current)
		if err != nil {
			return err
		}
		info, err := rootHandle.Lstat(current)
		if err != nil {
			return err
		}
		mode := info.Mode()
		if mode&(os.ModeSetuid|os.ModeSetgid|os.ModeSticky) != 0 {
			return fmt.Errorf("%s has setid or sticky mode", name)
		}
		record := contentEntry{Path: name, Size: info.Size()}
		switch {
		case mode.IsDir():
			directory, err := rootHandle.OpenFile(current, os.O_RDONLY|directoryReadFlags, 0)
			if err != nil {
				return err
			}
			securityErr := checkDirectorySecurity(directory, false)
			closeErr := directory.Close()
			if err := errors.Join(securityErr, closeErr); err != nil {
				return err
			}
			record.Type = "directory"
			record.Mode = 0o755
			record.Size = 0
		case mode.IsRegular():
			file, err := rootHandle.OpenFile(current, os.O_RDONLY|directoryReadFlags, 0)
			if err != nil {
				return err
			}
			openedInfo, err := file.Stat()
			if err != nil {
				file.Close()
				return err
			}
			if !openedInfo.Mode().IsRegular() || !os.SameFile(info, openedInfo) {
				file.Close()
				return fmt.Errorf("%s changed while opening", name)
			}
			if err := checkDirectorySecurity(file, false); err != nil {
				file.Close()
				return fmt.Errorf("%s: %w", name, err)
			}
			record.Type = "file"
			// Host access permissions are not portable content metadata.
			// Explicit payload inventories bind their declared modes during validation.
			record.Mode = 0o644
			record.Size = openedInfo.Size()
			if record.Size < 0 || record.Size > maxContentBytes-total {
				file.Close()
				return fmt.Errorf("content exceeds %d bytes", maxContentBytes)
			}
			total += record.Size
			hash := sha256.New()
			var data []byte
			if shouldRetainMetadata(name, record.Size) {
				var nextRetained int64
				nextRetained, err = addRetainedMetadata(retained, record.Size)
				if err != nil {
					file.Close()
					return err
				}
				data, err = io.ReadAll(io.LimitReader(io.TeeReader(file, hash), record.Size+1))
				if err == nil && int64(len(data)) != record.Size {
					err = fmt.Errorf("%s size changed while reading", name)
				}
				retained = nextRetained
			} else {
				var written int64
				written, err = io.Copy(hash, io.LimitReader(file, record.Size+1))
				if err == nil && written != record.Size {
					err = fmt.Errorf("%s size changed while reading", name)
				}
			}
			closeErr := file.Close()
			if err != nil {
				return err
			}
			if closeErr != nil {
				return closeErr
			}
			record.Digest = "sha256:" + hex.EncodeToString(hash.Sum(nil))
			record.Data = data
		case mode&os.ModeSymlink != 0:
			if err := checkDirectoryLink(); err != nil {
				return err
			}
			record.Type = "symlink"
			record.Mode = 0o777
			target, err := rootHandle.Readlink(current)
			if err != nil {
				return err
			}
			if err := validateLinkTarget(name, filepath.ToSlash(target)); err != nil {
				return err
			}
			record.LinkTarget = filepath.ToSlash(target)
			record.Size = 0
		default:
			return fmt.Errorf("%s has unsupported file type %s", name, mode.Type())
		}
		if err := set.add(record); err != nil {
			return err
		}
		return nil
	})
	if err != nil {
		return nil, err
	}
	return set, nil
}

func loadContentLayer(reader io.Reader) (*contentSet, error) {
	gzipReader, err := gzip.NewReader(reader)
	if err != nil {
		return nil, fmt.Errorf("content layer is not gzip: %w", err)
	}
	defer gzipReader.Close()
	if !gzipReader.ModTime.IsZero() {
		return nil, errors.New("content gzip modification time must be unset")
	}
	tarReader := tar.NewReader(gzipReader)
	set := &contentSet{entries: map[string]contentEntry{}, folded: map[string]string{}}
	regular := map[string]bool{}
	var total, retained int64
	count := 0
	for {
		header, err := tarReader.Next()
		if errors.Is(err, io.EOF) {
			break
		}
		if err != nil {
			return nil, fmt.Errorf("read content tar: %w", err)
		}
		if !header.ModTime.Equal(time.Unix(0, 0).UTC()) {
			return nil, fmt.Errorf("%s tar modification time must be the Unix epoch", header.Name)
		}
		if !header.AccessTime.IsZero() || !header.ChangeTime.IsZero() {
			return nil, fmt.Errorf("%s tar access and change times must be unset", header.Name)
		}
		count++
		if count > maxContentEntries {
			return nil, fmt.Errorf("content has more than %d entries", maxContentEntries)
		}
		rawName := header.Name
		if header.Typeflag == tar.TypeDir {
			rawName = strings.TrimSuffix(rawName, "/")
		}
		name, err := validateContentPath(rawName)
		if err != nil {
			return nil, err
		}
		if header.Mode&0o7000 != 0 {
			return nil, fmt.Errorf("%s has setid or sticky mode %#o", name, header.Mode)
		}
		if header.Mode&0o022 != 0 && (header.Typeflag == tar.TypeReg || header.Typeflag == tar.TypeLink) {
			return nil, fmt.Errorf("%s is group or world writable", name)
		}
		record := contentEntry{
			Path: name,
			Mode: uint32(header.Mode & 0o777),
			UID:  header.Uid,
			GID:  header.Gid,
			Size: header.Size,
		}
		switch header.Typeflag {
		case tar.TypeDir:
			record.Type = "directory"
			record.Size = 0
		case tar.TypeReg:
			record.Type = "file"
			if header.Size < 0 || header.Size > maxContentBytes-total {
				return nil, fmt.Errorf("content exceeds %d bytes", maxContentBytes)
			}
			total += header.Size
			hash := sha256.New()
			if shouldRetainMetadata(name, header.Size) {
				nextRetained, err := addRetainedMetadata(retained, header.Size)
				if err != nil {
					return nil, err
				}
				data, err := io.ReadAll(io.LimitReader(io.TeeReader(tarReader, hash), header.Size+1))
				if err != nil {
					return nil, err
				}
				if int64(len(data)) != header.Size {
					return nil, fmt.Errorf("%s size does not match tar header", name)
				}
				record.Data = data
				retained = nextRetained
			} else if written, err := io.CopyN(hash, tarReader, header.Size); err != nil || written != header.Size {
				if err == nil {
					err = io.ErrUnexpectedEOF
				}
				return nil, fmt.Errorf("read %s: %w", name, err)
			}
			record.Digest = "sha256:" + hex.EncodeToString(hash.Sum(nil))
			regular[name] = true
		case tar.TypeSymlink:
			record.Type = "symlink"
			if err := validateLinkTarget(name, header.Linkname); err != nil {
				return nil, err
			}
			record.LinkTarget = header.Linkname
			record.Size = 0
		case tar.TypeLink:
			record.Type = "hardlink"
			target, err := validateContentPath(header.Linkname)
			if err != nil {
				return nil, fmt.Errorf("%s hardlink target: %w", name, err)
			}
			if !regular[target] {
				return nil, fmt.Errorf("%s hardlink target %s is not an earlier regular file", name, target)
			}
			record.LinkTarget = target
			record.Size = 0
		default:
			return nil, fmt.Errorf("%s has unsupported tar type %d", name, header.Typeflag)
		}
		if err := set.add(record); err != nil {
			return nil, err
		}
	}
	written, err := io.CopyN(io.Discard, gzipReader, 1)
	if written != 0 {
		return nil, errors.New("content gzip contains data after the tar archive")
	}
	if err != nil && !errors.Is(err, io.EOF) {
		return nil, fmt.Errorf("finish content gzip stream: %w", err)
	}
	return set, nil
}

func (s *contentSet) add(entry contentEntry) error {
	if _, exists := s.entries[entry.Path]; exists {
		return fmt.Errorf("duplicate content path %s", entry.Path)
	}
	folded := foldCase(entry.Path)
	if existing, ok := s.folded[folded]; ok {
		return fmt.Errorf("case-folding path collision between %s and %s", existing, entry.Path)
	}
	s.entries[entry.Path] = entry
	s.folded[folded] = entry.Path
	return nil
}

func (s *contentSet) data(name string) ([]byte, error) {
	name, err := validateContentPath(name)
	if err != nil {
		return nil, err
	}
	entry, ok := s.entries[name]
	if !ok {
		return nil, fmt.Errorf("required file %s is missing", name)
	}
	if entry.Type != "file" {
		return nil, fmt.Errorf("%s is not a regular file", name)
	}
	if entry.Data == nil {
		return nil, fmt.Errorf("%s is not retained metadata", name)
	}
	return append([]byte(nil), entry.Data...), nil
}

func shouldRetainMetadata(name string, size int64) bool {
	return strings.HasSuffix(name, ".json") && size >= 0 && size <= maxJSONBytes
}

func addRetainedMetadata(retained, size int64) (int64, error) {
	if retained < 0 || size < 0 || size > maxRetainedMetadataBytes-retained {
		return 0, fmt.Errorf("retained metadata exceeds %d bytes", maxRetainedMetadataBytes)
	}
	return retained + size, nil
}

func validateContentPath(value string) (string, error) { return contract.ValidateContentPath(value) }

func validateLinkTarget(name, target string) error {
	if target == "" || len(target) > maxPathBytes || !utf8.ValidString(target) || strings.ContainsRune(target, '\x00') ||
		strings.Contains(target, "\\") || strings.HasPrefix(target, "/") {
		return fmt.Errorf("%s has unsafe link target %q", name, target)
	}
	resolved := path.Clean(path.Join(path.Dir(name), target))
	if resolved == "." || resolved == ".." || strings.HasPrefix(resolved, "../") {
		return fmt.Errorf("%s link target escapes the content root", name)
	}
	return nil
}
