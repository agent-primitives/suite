//go:build windows

package agentsuite

import (
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"testing"

	"golang.org/x/sys/windows"
)

func windowsFixtureUser(t *testing.T) *windows.SID {
	t.Helper()
	user, err := windows.GetCurrentProcessToken().GetTokenUser()
	if err != nil {
		t.Fatal(err)
	}
	return user.User.Sid
}

func windowsFixtureACL(t *testing.T, name, dacl string, protected bool) {
	t.Helper()
	user := windowsFixtureUser(t)
	sd, err := windows.SecurityDescriptorFromString("O:" + user.String() + "D:" + dacl)
	if err != nil {
		t.Fatal(err)
	}
	acl, _, err := sd.DACL()
	if err != nil {
		t.Fatal(err)
	}
	flags := windows.SECURITY_INFORMATION(windows.OWNER_SECURITY_INFORMATION | windows.DACL_SECURITY_INFORMATION)
	if protected {
		flags |= windows.PROTECTED_DACL_SECURITY_INFORMATION
	} else {
		flags |= windows.UNPROTECTED_DACL_SECURITY_INFORMATION
	}
	if err := windows.SetNamedSecurityInfo(name, windows.SE_FILE_OBJECT, flags, user, nil, acl, nil); err != nil {
		t.Fatal(err)
	}
}

// Fixture construction only: production must never repair input permissions.
func secureDirectoryFixture(t *testing.T, root string) {
	t.Helper()
	owner := windowsFixtureUser(t).String()
	if err := filepath.WalkDir(root, func(name string, entry fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if entry.Type()&os.ModeSymlink != 0 {
			t.Fatalf("fixture contains a symlink: %s", name)
		}
		windowsFixtureACL(t, name, "P(A;OICI;FA;;;"+owner+")", true)
		return nil
	}); err != nil {
		t.Fatal(err)
	}
}

func windowsCheckFixture(t *testing.T, name string, root, wantOK bool) {
	t.Helper()
	file, err := os.OpenFile(name, os.O_RDONLY|directoryReadFlags, 0)
	if err != nil {
		t.Fatal(err)
	}
	defer file.Close()
	if err := checkDirectorySecurity(file, root); (err == nil) != wantOK {
		t.Fatalf("checkDirectorySecurity(%s, root=%v) = %v; want success=%v", name, root, err, wantOK)
	}
}

func TestWindowsDirectorySecurityProtectedOwnerRoot(t *testing.T) {
	root := t.TempDir()
	name := filepath.Join(root, "payload")
	if err := os.WriteFile(name, []byte("fixture\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	secureDirectoryFixture(t, root)
	windowsCheckFixture(t, root, true, true)
	windowsCheckFixture(t, name, false, true)
}

func TestWindowsDirectorySecurityRefusals(t *testing.T) {
	owner := windowsFixtureUser(t).String()
	for _, tc := range []struct {
		name, dacl string
		protected  bool
	}{
		{"BroadExplicit", "P(A;;FA;;;" + owner + ")(A;;FR;;;WD)", true},
		{"UnprotectedRoot", "(A;;FA;;;" + owner + ")", false},
		{"NullDACL", "NO_ACCESS_CONTROL", true},
		{"UnsupportedObjectACE", "P(A;;FA;;;" + owner + ")(OA;;FR;00112233-4455-6677-8899-aabbccddeeff;;WD)", true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			root := t.TempDir()
			windowsFixtureACL(t, root, tc.dacl, tc.protected)
			windowsCheckFixture(t, root, true, false)
		})
	}
}

func TestWindowsDirectorySecurityInheritance(t *testing.T) {
	owner := windowsFixtureUser(t)
	for _, broad := range []bool{false, true} {
		name := "OwnerOnlyChild"
		grants := "P(A;OICI;FA;;;" + owner.String() + ")"
		if broad {
			name, grants = "BroadInherited", grants+"(A;OICI;FR;;;WD)"
		}
		t.Run(name, func(t *testing.T) {
			root := t.TempDir()
			windowsFixtureACL(t, root, grants, true)
			windowsCheckFixture(t, root, true, !broad)
			child := filepath.Join(root, "child")
			if err := os.Mkdir(child, 0o700); err != nil {
				t.Fatal(err)
			}
			if err := windows.SetNamedSecurityInfo(child, windows.SE_FILE_OBJECT, windows.OWNER_SECURITY_INFORMATION, owner, nil, nil, nil); err != nil {
				t.Fatal(err)
			}
			sd, err := windows.GetNamedSecurityInfo(child, windows.SE_FILE_OBJECT, windows.DACL_SECURITY_INFORMATION)
			if err != nil {
				t.Fatal(err)
			}
			control, _, err := sd.Control()
			if err != nil || control&windows.SE_DACL_PROTECTED != 0 {
				t.Fatalf("child DACL is not unprotected: control=%x err=%v", control, err)
			}
			dacl, _, err := sd.DACL()
			if err != nil || dacl == nil || dacl.AceCount == 0 {
				t.Fatalf("missing inherited child grants: %v", err)
			}
			for i := uint32(0); i < uint32(dacl.AceCount); i++ {
				var ace *windows.ACCESS_ALLOWED_ACE
				if err := windows.GetAce(dacl, i, &ace); err != nil || ace.Header.AceFlags&windows.INHERITED_ACE == 0 {
					t.Fatalf("child ACE %d is not inherited: %v", i, err)
				}
			}
			windowsCheckFixture(t, child, false, !broad)
		})
	}
}

func TestWindowsDirectorySecurityInvalidHandle(t *testing.T) {
	file, err := os.Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	file.Close()
	if err := checkDirectorySecurity(file, true); err == nil {
		t.Fatal("closed handle was accepted")
	}
	read, write, err := os.Pipe()
	if err != nil {
		t.Fatal(err)
	}
	defer read.Close()
	defer write.Close()
	if err := checkDirectorySecurity(read, false); err == nil {
		t.Fatal("pipe was accepted")
	}
}

func TestWindowsDirectorySecurityJunction(t *testing.T) {
	root := t.TempDir()
	secureDirectoryFixture(t, root)
	parent := t.TempDir()
	secureDirectoryFixture(t, parent)
	junction := filepath.Join(parent, "junction")
	if output, err := exec.Command("cmd", "/c", "mklink", "/J", junction, root).CombinedOutput(); err != nil {
		t.Fatalf("create junction: %v: %s", err, output)
	}
	windowsCheckFixture(t, junction, false, false)
	if _, err := loadDirectory(parent); err == nil {
		t.Fatal("loose directory containing a junction was accepted")
	}
}
