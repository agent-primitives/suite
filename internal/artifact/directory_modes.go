package artifact

import "fmt"

// bindDirectoryMode applies authored payload metadata, never host permission bits.
// Archived content is already authoritative and must still match its inventory.
func (s *contentSet) bindDirectoryMode(name string, mode uint32) error {
	if s.sourceType != "directory" {
		return nil
	}
	if previous, ok := s.declaredModes[name]; ok && previous != mode {
		return fmt.Errorf("content path %s has conflicting declared mode", name)
	}
	if s.declaredModes == nil {
		s.declaredModes = make(map[string]uint32)
	}
	s.declaredModes[name] = mode
	entry := s.entries[name]
	entry.Mode = mode
	s.entries[name] = entry
	return nil
}
