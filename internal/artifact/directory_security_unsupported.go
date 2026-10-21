//go:build !unix && !windows

package artifact

import (
	"errors"
	"os"
)

const directoryReadFlags = 0

// Unknown host security semantics cannot establish the loose-directory boundary.
func checkDirectorySecurity(_ *os.File, _ bool) error {
	return errors.New("loose-directory security is unsupported on this platform")
}

func checkDirectoryLink() error {
	return errors.New("loose-directory security is unsupported on this platform")
}
