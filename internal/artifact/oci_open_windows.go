package artifact

import "syscall"

// Go's Windows open passes this native flag through to CreateFile.
const ociReadFlags = syscall.FILE_FLAG_OPEN_REPARSE_POINT
