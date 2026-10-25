//go:build unix

package artifact

import (
	"os"
	"path/filepath"
	"testing"

	"golang.org/x/sys/unix"
)

const directoryCasePlatform = "posix"

func directoryFixtureAlias(t *testing.T, alias, target string) {
	t.Helper()
	if err := os.Symlink(target, alias); err != nil {
		t.Fatal(err)
	}
}

func directoryFixtureMutation(t *testing.T, root string, c directoryAccessCase) {
	t.Helper()
	name := filepath.Join(root, filepath.FromSlash(c.Path))
	switch c.Kind {
	case "symlink":
		if err := os.Symlink(c.Target, name); err != nil {
			t.Fatal(err)
		}
	case "fifo":
		if err := unix.Mkfifo(name, 0600); err != nil {
			t.Fatal(err)
		}
	case "root-mode", "file-mode", "directory-mode":
		if c.Kind == "root-mode" {
			name = root
		}
		mode := os.FileMode(c.Mode & 0777)
		if c.Mode&04000 != 0 {
			mode |= os.ModeSetuid
		}
		if c.Mode&02000 != 0 {
			mode |= os.ModeSetgid
		}
		if c.Mode&01000 != 0 {
			mode |= os.ModeSticky
		}
		if err := os.Chmod(name, mode); err != nil {
			t.Fatal(err)
		}
	default:
		t.Fatalf("unknown POSIX directory fixture: %s", c.Kind)
	}
}
