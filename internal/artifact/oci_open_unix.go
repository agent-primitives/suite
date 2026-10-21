//go:build unix

package artifact

import "syscall"

const ociReadFlags = syscall.O_NOFOLLOW | syscall.O_NONBLOCK
