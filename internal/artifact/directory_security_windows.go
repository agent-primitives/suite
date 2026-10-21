//go:build windows

package artifact

import (
	"fmt"
	"os"
	"syscall"
	"unsafe"

	"golang.org/x/sys/windows"
)

// Go passes this flag through to CreateFile, opening the reparse object itself.
const directoryReadFlags = syscall.FILE_FLAG_OPEN_REPARSE_POINT

func checkDirectoryLink() error {
	return fmt.Errorf("directory input symlinks and reparse points are not supported on Windows")
}

func checkDirectorySecurity(file *os.File, root bool) error {
	handle := windows.Handle(file.Fd())
	kind, err := windows.GetFileType(handle)
	if err != nil {
		return fmt.Errorf("query directory input type: %w", err)
	}
	if kind != windows.FILE_TYPE_DISK {
		return fmt.Errorf("directory input is not a disk file or directory")
	}
	var info windows.ByHandleFileInformation
	if err := windows.GetFileInformationByHandle(handle, &info); err != nil {
		return fmt.Errorf("query directory input attributes: %w", err)
	}
	if info.FileAttributes&(windows.FILE_ATTRIBUTE_REPARSE_POINT|windows.FILE_ATTRIBUTE_DEVICE) != 0 {
		return fmt.Errorf("directory input is a reparse point or device")
	}
	if root && info.FileAttributes&windows.FILE_ATTRIBUTE_DIRECTORY == 0 {
		return fmt.Errorf("directory input root is not a directory")
	}
	var volumeFlags uint32
	if err := windows.GetVolumeInformationByHandle(handle, nil, 0, nil, nil, &volumeFlags, nil, 0); err != nil {
		return fmt.Errorf("query directory input filesystem: %w", err)
	}
	if volumeFlags&windows.FILE_PERSISTENT_ACLS == 0 {
		return fmt.Errorf("directory input filesystem does not enforce persistent ACLs")
	}
	user, err := windows.GetCurrentProcessToken().GetTokenUser()
	if err != nil {
		return fmt.Errorf("query directory input current user: %w", err)
	}
	sd, err := windows.GetSecurityInfo(handle, windows.SE_FILE_OBJECT, windows.OWNER_SECURITY_INFORMATION|windows.DACL_SECURITY_INFORMATION)
	if err != nil {
		return fmt.Errorf("query directory input security: %w", err)
	}
	if !sd.IsValid() {
		return fmt.Errorf("directory input has an invalid security descriptor")
	}
	owner, _, err := sd.Owner()
	if err != nil {
		return fmt.Errorf("query directory input owner: %w", err)
	}
	// A token's default owner may be a group (notably Administrators).
	if owner == nil || !owner.IsValid() || !owner.Equals(user.User.Sid) {
		return fmt.Errorf("directory input owner is not the current user")
	}
	control, _, err := sd.Control()
	if err != nil {
		return fmt.Errorf("query directory input DACL control: %w", err)
	}
	if root && control&windows.SE_DACL_PROTECTED == 0 {
		return fmt.Errorf("directory input root DACL is not protected")
	}
	dacl, _, err := sd.DACL()
	if err != nil {
		return fmt.Errorf("query directory input DACL: %w", err)
	}
	if control&windows.SE_DACL_PRESENT == 0 || dacl == nil {
		return fmt.Errorf("directory input has a missing or null DACL")
	}
	for i := uint32(0); i < uint32(dacl.AceCount); i++ {
		var ace *windows.ACCESS_ALLOWED_ACE
		if err := windows.GetAce(dacl, i, &ace); err != nil {
			return fmt.Errorf("query directory input ACE %d: %w", i, err)
		}
		// Recognize only ordinary allow ACEs. Object/callback/deny forms are
		// conservatively refused rather than approximating access evaluation.
		if ace == nil || ace.Header.AceType != windows.ACCESS_ALLOWED_ACE_TYPE || ace.Header.AceFlags&^uint8(windows.VALID_INHERIT_FLAGS) != 0 || ace.Header.AceSize < 16 {
			return fmt.Errorf("directory input has an unsupported ACE")
		}
		// GetAce returns the native ACE; its SID begins at SidStart, not at
		// a separately allocated pointer. Eight bytes is the SID header size.
		sid := (*windows.SID)(unsafe.Pointer(&ace.SidStart))
		if !sid.IsValid() || int(unsafe.Offsetof(ace.SidStart))+sid.Len() > int(ace.Header.AceSize) || !sid.Equals(owner) {
			return fmt.Errorf("directory input has an invalid or non-owner grant")
		}
	}
	return nil
}
