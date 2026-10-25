package core

import (
	"encoding/json"
	"reflect"
	"testing"
)

func TestInventoryFileSizeSerialization(t *testing.T) {
	const emptyDigest = "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
	for _, c := range []struct {
		name  string
		entry InventoryEntry
		want  string
	}{
		{"empty file", InventoryEntry{Path: "empty", Type: "file", Mode: 0o644, Digest: emptyDigest},
			`{"digest":"sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","gid":0,"mode":420,"path":"empty","size":0,"type":"file","uid":0}`},
		{"nonempty file", InventoryEntry{Path: "data", Type: "file", Mode: 0o644, Size: 3, Digest: "sha256:ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"},
			`{"digest":"sha256:ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad","gid":0,"mode":420,"path":"data","size":3,"type":"file","uid":0}`},
		{"directory", InventoryEntry{Path: "dir", Type: "directory", Mode: 0o755},
			`{"gid":0,"mode":493,"path":"dir","type":"directory","uid":0}`},
		{"link", InventoryEntry{Path: "link", Type: "hardlink", Mode: 0o644, LinkTarget: "data"},
			`{"gid":0,"linkTarget":"data","mode":420,"path":"link","type":"hardlink","uid":0}`},
	} {
		t.Run(c.name, func(t *testing.T) {
			got, err := Marshal(c.entry)
			if err != nil || string(got) != c.want {
				t.Fatalf("canonical inventory = %s, %v; want %s", got, err, c.want)
			}
			raw, err := json.Marshal(c.entry)
			if err != nil {
				t.Fatal(err)
			}
			var actual, expected map[string]any
			if err := json.Unmarshal(raw, &actual); err != nil {
				t.Fatal(err)
			}
			if err := json.Unmarshal([]byte(c.want), &expected); err != nil {
				t.Fatal(err)
			}
			if !reflect.DeepEqual(actual, expected) {
				t.Fatalf("standard JSON inventory = %s, want %s", raw, c.want)
			}
			var decoded InventoryEntry
			if err := Unmarshal(got, &decoded); err != nil || decoded != c.entry {
				t.Fatalf("inventory roundtrip = %+v, %v; want %+v", decoded, err, c.entry)
			}
		})
	}
}
