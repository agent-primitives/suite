//go:build unix

package artifact

import (
	"errors"
	"os"
)

const directoryReadFlags = ociReadFlags

// Host access safety is independent of canonical content modes.
func checkDirectorySecurity(file *os.File, _ bool) error {
	info, err := file.Stat()
	if err != nil {
		return err
	}
	mode := info.Mode()
	if mode&(os.ModeSetuid|os.ModeSetgid|os.ModeSticky) != 0 || (mode.IsRegular() || mode.IsDir()) && mode.Perm()&0o022 != 0 {
		return errors.New("content has unsafe file mode")
	}
	return nil
}

func checkDirectoryLink() error { return nil }
