//go:build darwin || dragonfly || freebsd || linux || netbsd || openbsd

package agentsuite

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
	"testing"
	"time"
)

// Each potentially blocking call runs in a killable process, not a goroutine
// that could survive its test. A deadline or child failure is always a failure.
func TestOCILayoutRejectsSpecialFiles(t *testing.T) {
	const childEnv = "AGENTSUITE_OCI_SPECIAL_CASE"
	const sentinel = "OCI_SPECIAL_FILES_OK:"
	type testCase struct{ target, kind string }
	var cases []testCase
	for _, target := range []string{"oci-layout", "index.json", "manifest", "config", "layer"} {
		for _, kind := range []string{"fifo", "symlink-fifo", "directory", "socket", "symlink-regular"} {
			cases = append(cases, testCase{target, kind})
		}
	}
	for _, target := range []string{"oci-layout", "index.json"} {
		cases = append(cases, testCase{target, "dangling"})
	}
	for _, target := range []string{"blobs", "blobs/sha256"} {
		for _, kind := range []string{"fifo", "symlink-directory"} {
			cases = append(cases, testCase{target, kind})
		}
	}
	cases = append(cases, testCase{"root", "fifo"}, testCase{"index.json", "missing"}, testCase{"device", "dev-null"})

	if selected := os.Getenv(childEnv); selected != "" {
		for _, tc := range cases {
			if selected == tc.target+"/"+tc.kind {
				checkOCISpecialFile(t, tc.target, tc.kind)
				if !t.Failed() {
					fmt.Println(sentinel + selected)
				}
				return
			}
		}
		t.Fatalf("unknown child case %q", selected)
	}

	executable, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	for _, tc := range cases {
		name := tc.target + "/" + tc.kind
		t.Run(name, func(t *testing.T) {
			ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
			defer cancel()
			cmd := exec.CommandContext(ctx, executable, "-test.run=^TestOCILayoutRejectsSpecialFiles$", "-test.v")
			cmd.Env = append(os.Environ(), childEnv+"="+name)
			output, err := cmd.CombinedOutput()
			if ctx.Err() != nil {
				t.Fatalf("child exceeded 5s; OCI file open may have blocked: %v\n%s", ctx.Err(), output)
			}
			if err != nil {
				t.Fatalf("child failed: %v\n%s", err, output)
			}
			if !bytes.Contains(output, []byte(sentinel+name+"\n")) {
				t.Fatalf("child did not complete its assertions:\n%s", output)
			}
		})
	}
}

func TestOCILayoutRootDirectoryAlias(t *testing.T) {
	layout, expected, evidence := evidenceFixture(t, nil)
	alias := filepath.Join(t.TempDir(), "layout")
	if err := os.Symlink(layout, alias); err != nil {
		t.Fatal(err)
	}
	evidenceCode(t, alias, expected, evidenceBytes(t, evidence), "")
	if report, err := ValidatePath(alias); err != nil || report == nil {
		t.Fatalf("directory alias: report=%+v error=%v", report, err)
	}
}

func checkOCISpecialFile(t *testing.T, target, kind string) {
	t.Helper()
	layout, expected, evidence := evidenceFixture(t, nil)
	data := evidenceBytes(t, evidence)
	summary, err := VerifyEvaluation(layout, expected, bytes.NewReader(data))
	if err != nil || summary == nil {
		t.Fatalf("baseline fixture must verify before mutation: summary=%+v error=%v", summary, err)
	}
	if report, err := ValidatePath(layout); err != nil || report == nil {
		t.Fatalf("baseline fixture must validate: report=%+v error=%v", report, err)
	}
	t.Log("valid fixture verified before mutation")

	if kind == "dev-null" {
		info, err := os.Lstat("/dev/null")
		if err != nil {
			t.Fatal(err)
		}
		if info.Mode()&os.ModeDevice == 0 {
			t.Fatalf("/dev/null is not an existing device: %v", info.Mode())
		}
		if data, err := readRegularFile("/dev/null", maxJSONBytes); err == nil || data != nil {
			t.Fatalf("device read returned data=%q error=%v; want refusal", data, err)
		}
		return
	}

	// Resolve actual fixture descriptors rather than duplicating their hashes.
	readJSON := func(name string, value any) {
		t.Helper()
		raw, err := os.ReadFile(name)
		if err != nil {
			t.Fatal(err)
		}
		if err := json.Unmarshal(raw, value); err != nil {
			t.Fatal(err)
		}
	}
	blobPath := func(d ociDescriptor) string {
		return filepath.Join(layout, "blobs", "sha256", strings.TrimPrefix(d.Digest, "sha256:"))
	}
	var index ociIndex
	readJSON(filepath.Join(layout, "index.json"), &index)
	if len(index.Manifests) != 1 {
		t.Fatalf("fixture has %d manifests; want one", len(index.Manifests))
	}
	var manifest ociManifest
	readJSON(blobPath(index.Manifests[0]), &manifest)
	if len(manifest.Layers) != 1 {
		t.Fatalf("fixture has %d layers; want one", len(manifest.Layers))
	}
	paths := map[string]string{
		"root": layout, "oci-layout": filepath.Join(layout, "oci-layout"),
		"index.json": filepath.Join(layout, "index.json"),
		"manifest":   blobPath(index.Manifests[0]), "config": blobPath(manifest.Config),
		"layer": blobPath(manifest.Layers[0]), "blobs": filepath.Join(layout, "blobs"),
		"blobs/sha256": filepath.Join(layout, "blobs", "sha256"),
	}
	name, ok := paths[target]
	if !ok {
		t.Fatalf("unknown fixture target %q", target)
	}
	replaceOCISpecialFile(t, name, kind)

	t.Log("checking VerifyEvaluation refusal")
	summary, err = VerifyEvaluation(layout, expected, bytes.NewReader(data))
	var refusal *EvidenceRefusal
	if summary != nil || !errors.As(err, &refusal) || refusal.Code != "artifact" {
		t.Errorf("VerifyEvaluation: summary=%+v error=%v; want nil summary and typed artifact refusal", summary, err)
	}
	t.Log("checking ValidatePath refusal")
	if report, err := ValidatePath(layout); err == nil || report != nil {
		t.Errorf("ValidatePath: report=%+v error=%v; want nil report and error", report, err)
	}
	if kind == "dangling" {
		// Auto-detection must recognize the entry, not fall back to loose content.
		content, err := loadPathContent(layout)
		if err == nil || content != nil {
			t.Errorf("dangling OCI metadata fell back to content: content=%+v error=%v", content, err)
		}
		if target == "oci-layout" && (err == nil || !strings.HasPrefix(err.Error(), "read oci-layout: ")) {
			t.Errorf("dangling OCI marker did not select the OCI loader: %v", err)
		}
	}
}

func replaceOCISpecialFile(t *testing.T, name, kind string) {
	t.Helper()
	external := filepath.Join(t.TempDir(), "target")
	if kind == "symlink-directory" {
		// Preserve a valid blob tree outside the layout: rejection must concern
		// the parent link, not missing blobs or invalid descriptor bytes.
		if err := os.Rename(name, external); err != nil {
			t.Fatal(err)
		}
	} else {
		if kind == "symlink-regular" {
			data, err := os.ReadFile(name)
			if err != nil {
				t.Fatal(err)
			}
			if err := os.WriteFile(external, data, 0o600); err != nil {
				t.Fatal(err)
			}
		}
		if err := os.RemoveAll(name); err != nil {
			t.Fatal(err)
		}
	}
	var err error
	switch kind {
	case "fifo":
		err = syscall.Mkfifo(name, 0o600)
	case "symlink-fifo":
		if err := syscall.Mkfifo(external, 0o600); err != nil {
			t.Fatal(err)
		}
		err = os.Symlink(external, name)
	case "symlink-regular", "symlink-directory", "dangling":
		err = os.Symlink(external, name)
	case "directory":
		err = os.Mkdir(name, 0o700)
	case "socket":
		// A relative bind avoids Unix socket address limits without assuming
		// a particular temporary filesystem. This child process is isolated.
		t.Chdir(filepath.Dir(name))
		listener, listenErr := net.ListenUnix("unix", &net.UnixAddr{Name: filepath.Base(name), Net: "unix"})
		if listenErr != nil {
			t.Fatal(listenErr)
		}
		listener.SetUnlinkOnClose(false)
		if err := listener.Close(); err != nil {
			t.Fatal(err)
		}
	case "missing":
		// The original entry has already been removed.
	default:
		t.Fatalf("unknown special-file kind %q", kind)
	}
	if err != nil {
		t.Fatalf("create %s at %s: %v", kind, name, err)
	}
}
