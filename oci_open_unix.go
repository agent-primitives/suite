//go:build unix

package agentsuite

import "syscall"

const ociReadFlags = syscall.O_NOFOLLOW | syscall.O_NONBLOCK
