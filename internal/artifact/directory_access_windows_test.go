//go:build windows

package artifact

import (
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"

	"golang.org/x/sys/windows"
)

const directoryCasePlatform = "windows"

func directoryFixtureAlias(t *testing.T, alias, target string) {
	t.Helper()
	if output, err := exec.Command("cmd", "/c", "mklink", "/J", alias, target).CombinedOutput(); err != nil {
		t.Fatalf("create fixture junction: %v: %s", err, output)
	}
}

func directoryFixtureMutation(t *testing.T, root string, c directoryAccessCase) {
	t.Helper()
	switch c.Kind {
	case "acl":
		owner := windowsFixtureUser(t).String()
		windowsFixtureACL(t, root, strings.ReplaceAll(c.DACL, "{owner}", owner), c.Protected)
	case "inherited-owner":
		name := filepath.Join(root, "inherited")
		if err := os.Mkdir(name, 0700); err != nil {
			t.Fatal(err)
		}
		if err := windows.SetNamedSecurityInfo(name, windows.SE_FILE_OBJECT, windows.OWNER_SECURITY_INFORMATION, windowsFixtureUser(t), nil, nil, nil); err != nil {
			t.Fatal(err)
		}
	case "junction":
		directoryFixtureAlias(t, filepath.Join(root, c.Path), filepath.Join(root, c.Target))
	default:
		t.Fatalf("unknown Windows directory fixture: %s", c.Kind)
	}
}
