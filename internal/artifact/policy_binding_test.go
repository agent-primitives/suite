package artifact

import (
	"archive/tar"
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/agent-primitives/suite/policy"
)

const (
	bindingMediaV1 = "application/vnd.agentsuite.policy.v1+json"
	bindingMediaV2 = "application/vnd.agentsuite.policy.v2+json"
	bindingV1      = `{"denyWritePaths":["/z","/a","/z"],"requiredCapabilities":["filesystem/deny-write/v1"],"version":"agentsuite.policy/v1"}`
	bindingV2      = `{"network":{"egressAllow":[{"address":"192.0.2.2","port":443,"protocol":"TCP"},{"address":"192.0.2.1","port":80,"protocol":"TCP"}]},"requiredCapabilities":["network/egress-allow/v1"],"version":"agentsuite.policy/v2"}`
	bindingDenyAll = `{"network":{"egressAllow":[]},"requiredCapabilities":["network/egress-allow/v1"],"version":"agentsuite.policy/v2"}`
)

// These raw Agent maps let the positive test fail before Agent.Policy exists.
func TestPolicyBindingAcceptsAuthoredPolicies(t *testing.T) {
	for _, tt := range []struct{ name, media, data string }{
		{"v1", bindingMediaV1, bindingV1},
		{"v2", bindingMediaV2, bindingV2},
		{"deny all", bindingMediaV2, bindingDenyAll},
	} {
		t.Run(tt.name, func(t *testing.T) {
			root, ref := writePolicyBindingSuite(t, tt.media, []byte(tt.data))
			for _, source := range policyBindingSources(t, root) {
				report, err := ValidatePath(source)
				if err != nil {
					t.Fatalf("ValidatePath(%s): %v", source, err)
				}
				if len(report.Capabilities) != 0 {
					t.Fatalf("policy must not add tool capabilities: %v", report.Capabilities)
				}
			}
			stored := policyBindingRead(t, root, ref.Path)
			if !bytes.Equal(stored, []byte(tt.data)) {
				t.Fatalf("authored policy was rewritten: %s", stored)
			}
			var agent Agent
			if err := Unmarshal(policyBindingRead(t, root, "agents/writer.json"), &agent); err != nil {
				t.Fatal(err)
			}
			roundtrip, err := Marshal(agent)
			if err != nil {
				t.Fatal(err)
			}
			if !bytes.Equal(roundtrip, policyBindingRead(t, root, "agents/writer.json")) {
				t.Fatalf("Agent round-trip lost policy: %s", roundtrip)
			}
		})
	}
}

func TestPolicyBindingRejectsReferenceShapes(t *testing.T) {
	for _, tt := range []struct {
		name   string
		mutate func(map[string]any, map[string]any) any
		want   string
	}{
		{"null", func(_, _ map[string]any) any { return nil }, "policy must not be null"},
		{"array", func(_, _ map[string]any) any { return []any{} }, "cannot unmarshal"},
		{"missing path", func(r, _ map[string]any) any { delete(r, "path"); return r }, "policy must be policies/writer.json"},
		{"null path", func(r, _ map[string]any) any { r["path"] = nil; return r }, `field "path": null is not allowed`},
		{"unknown ref field", func(r, _ map[string]any) any { r["unknown"] = true; return r }, "unknown field"},
		{"missing descriptor", func(r, _ map[string]any) any { delete(r, "descriptor"); return r }, "digest is invalid"},
		{"null descriptor", func(r, _ map[string]any) any { r["descriptor"] = nil; return r }, `field "descriptor": null is not allowed`},
		{"missing digest", func(r, d map[string]any) any { delete(d, "digest"); return r }, "missing required field"},
		{"missing size", func(r, d map[string]any) any { delete(d, "size"); return r }, "missing required field"},
		{"missing media", func(r, d map[string]any) any { delete(d, "mediaType"); return r }, "missing required field"},
		{"null digest", func(r, d map[string]any) any { d["digest"] = nil; return r }, `field "digest": null is not allowed`},
		{"null size", func(r, d map[string]any) any { d["size"] = nil; return r }, `field "size": null is not allowed`},
		{"null media", func(r, d map[string]any) any { d["mediaType"] = nil; return r }, `field "mediaType": null is not allowed`},
		{"unknown descriptor field", func(r, d map[string]any) any { d["unknown"] = true; return r }, "unknown field"},
		{"negative size", func(r, d map[string]any) any { d["size"] = -1; return r }, "size is invalid"},
		{"wrong size", func(r, d map[string]any) any { d["size"] = 1; return r }, "digest mismatch"},
		{"invalid digest", func(r, d map[string]any) any { d["digest"] = "not-a-digest"; return r }, "digest is invalid"},
		{"wrong digest", func(r, d map[string]any) any { d["digest"] = "sha256:" + strings.Repeat("0", 64); return r }, "digest mismatch"},
		{"wrong media", func(r, d map[string]any) any { d["mediaType"] = MediaTypeAgent; return r }, "mediaType"},
		{"version mismatch", func(r, d map[string]any) any { d["mediaType"] = bindingMediaV2; return r }, "version"},
	} {
		t.Run(tt.name, func(t *testing.T) {
			root, ref := writePolicyBindingSuite(t, bindingMediaV1, []byte(bindingV1))
			data, err := json.Marshal(ref)
			if err != nil {
				t.Fatal(err)
			}
			var raw map[string]any
			if err := json.Unmarshal(data, &raw); err != nil {
				t.Fatal(err)
			}
			value := tt.mutate(raw, raw["descriptor"].(map[string]any))
			bindPolicyAgent(t, root, "writer", func(agent map[string]any) { agent["policy"] = value })
			assertPolicyBindingRejected(t, root, tt.want)
		})
	}
	root := writeMinimalSuite(t)
	bindPolicyAgent(t, root, "writer", func(agent map[string]any) { agent["unknown"] = true })
	assertPolicyBindingRejected(t, root, "unknown field")
}

func TestPolicyBindingRejectsInvalidDocuments(t *testing.T) {
	for _, tt := range []struct{ name, media, data, want string }{
		{"v1 empty paths", bindingMediaV1, strings.Replace(bindingV1, `["/z","/a","/z"]`, `[]`, 1), "denyWritePaths"},
		{"v1 relative path", bindingMediaV1, strings.Replace(bindingV1, `"/a"`, `"a"`, 1), "absolute"},
		{"v1 missing capability", bindingMediaV1, `{"denyWritePaths":["/a"],"version":"agentsuite.policy/v1"}`, "requiredCapabilities"},
		{"v1 unknown", bindingMediaV1, strings.Replace(bindingV1, `"version":`, `"unknown":true,"version":`, 1), "unknown field"},
		{"v1 network", bindingMediaV1, strings.Replace(bindingV1, `"version":`, `"network":null,"version":`, 1), "unknown field"},
		{"v2 missing network", bindingMediaV2, `{"requiredCapabilities":["network/egress-allow/v1"],"version":"agentsuite.policy/v2"}`, "network is required"},
		{"v2 null list", bindingMediaV2, strings.Replace(bindingDenyAll, `[]`, `null`, 1), "non-null list"},
		{"v2 wrong protocol", bindingMediaV2, strings.Replace(bindingV2, `"TCP"`, `"UDP"`, 1), "protocol"},
		{"v2 unknown", bindingMediaV2, strings.Replace(bindingV2, `"port":443`, `"port":443,"unknown":true`, 1), "unknown field"},
		{"v2 filesystem", bindingMediaV2, strings.Replace(bindingDenyAll, `"version":`, `"denyWritePaths":[],"version":`, 1), "unknown field"},
		{"v2 fractional port", bindingMediaV2, strings.Replace(bindingV2, `443`, `443.00000000000000000001`, 1), "port must be an integer"},
		{"v2 enormous exponent", bindingMediaV2, strings.Replace(bindingV2, `443`, `1e9999`, 1), "Number out of range"},
		{"v2 wrong version media", bindingMediaV1, bindingDenyAll, "version"},
		{"unsupported version", bindingMediaV1, strings.Replace(bindingV1, `policy/v1`, `policy/v3`, 1), "unsupported policy version"},
		{"duplicate field", bindingMediaV1, strings.Replace(bindingV1, `"version":`, `"version":"agentsuite.policy/v1","version":`, 1), "duplicate"},
		{"noncanonical raw descriptor", bindingMediaV1, " " + bindingV1, "canonical"},
		{"not JSON", bindingMediaV1, `{`, "policy"},
	} {
		t.Run(tt.name, func(t *testing.T) {
			// Raw descriptors deliberately preserve invalid number lexemes and
			// whitespace, so canonicalization cannot hide a semantic failure.
			root, _ := writePolicyBindingSuite(t, tt.media, []byte(tt.data))
			assertPolicyBindingRejected(t, root, tt.want)
		})
	}
}

func TestPolicyBindingChecksDescriptorsBeforeDecoding(t *testing.T) {
	for _, tt := range []struct {
		name   string
		mutate func(*Descriptor)
		want   string
	}{
		{"invalid digest", func(d *Descriptor) { d.Digest = "invalid" }, "digest is invalid"},
		{"negative size", func(d *Descriptor) { d.Size = -1 }, "size is invalid"},
		{"wrong media", func(d *Descriptor) { d.MediaType = MediaTypeAgent }, "mediaType"},
		{"wrong hash", func(d *Descriptor) { d.Digest = "sha256:" + strings.Repeat("0", 64) }, "digest mismatch"},
		{"wrong size", func(d *Descriptor) { d.Size++ }, "digest mismatch"},
	} {
		t.Run(tt.name, func(t *testing.T) {
			root, ref := writePolicyBindingSuite(t, bindingMediaV1, []byte("{"))
			tt.mutate(&ref.Descriptor)
			bindPolicyAgent(t, root, "writer", func(agent map[string]any) { agent["policy"] = ref })
			assertPolicyBindingRejected(t, root, tt.want)
		})
	}
}

func TestPolicyBindingRejectsUnownedContent(t *testing.T) {
	for _, tt := range []struct {
		name   string
		mutate func(*testing.T, string, *FileRef)
		want   string
	}{
		{"missing", func(t *testing.T, root string, ref *FileRef) {
			if err := os.Remove(filepath.Join(root, ref.Path)); err != nil {
				t.Fatal(err)
			}
		}, "is missing"},
		{"oversized", func(t *testing.T, root string, ref *FileRef) {
			data := bytes.Repeat([]byte(" "), maxJSONBytes+1)
			mustWrite(t, root, ref.Path, data)
			ref.Descriptor = rawPolicyDescriptor(bindingMediaV1, data)
		}, "not retained metadata"},
		{"cross agent", func(_ *testing.T, _ string, ref *FileRef) { ref.Path = "policies/reviewer.json" }, "policy must be policies/writer.json"},
		{"outside namespace", func(t *testing.T, root string, ref *FileRef) {
			ref.Path = "other.json"
			mustWrite(t, root, ref.Path, []byte(bindingV1))
		}, "policy must be policies/writer.json"},
		{"orphan file", func(t *testing.T, root string, _ *FileRef) {
			mustWrite(t, root, "policies/extra.json", []byte(bindingV1))
		}, "orphaned"},
		{"extra directory", func(t *testing.T, root string, _ *FileRef) {
			if err := os.Mkdir(filepath.Join(root, "policies/extra"), 0o755); err != nil {
				t.Fatal(err)
			}
		}, "orphaned"},
		{"nested file", func(t *testing.T, root string, _ *FileRef) {
			mustWrite(t, root, "policies/nested/policy.json", []byte(bindingV1))
		}, "orphaned"},
		{"stale policy bytes", func(t *testing.T, root string, ref *FileRef) {
			mustWrite(t, root, ref.Path, []byte(strings.Replace(bindingV1, `"/a"`, `"/b"`, 1)))
		}, "digest mismatch"},
		{"noncanonical canonical descriptor", func(t *testing.T, root string, ref *FileRef) { mustWrite(t, root, ref.Path, []byte(" "+bindingV1)) }, "digest mismatch"},
	} {
		t.Run(tt.name, func(t *testing.T) {
			root, ref := writePolicyBindingSuite(t, bindingMediaV1, []byte(bindingV1))
			tt.mutate(t, root, &ref)
			bindPolicyAgent(t, root, "writer", func(agent map[string]any) { agent["policy"] = ref })
			assertPolicyBindingRejected(t, root, tt.want)
		})
	}
	for _, name := range []string{"policies", "policies/writer.json", "policies/extra.json"} {
		t.Run("symlink "+name, func(t *testing.T) {
			root, _ := writePolicyBindingSuite(t, bindingMediaV1, []byte(bindingV1))
			target := "writer.json"
			if name == "policies" {
				if err := os.Rename(filepath.Join(root, "policies"), filepath.Join(root, "real-policies")); err != nil {
					t.Fatal(err)
				}
				target = "real-policies"
			} else if name == "policies/writer.json" {
				if err := os.Remove(filepath.Join(root, name)); err != nil {
					t.Fatal(err)
				}
				target = "../instructions/writer.md"
			}
			if err := os.Symlink(target, filepath.Join(root, name)); err != nil {
				t.Fatal(err)
			}
			want := "not a regular file"
			if name == "policies" {
				want = "is missing"
			}
			if name == "policies/extra.json" {
				want = "orphaned"
			}
			assertPolicyBindingRejected(t, root, want)
		})
	}
}

func TestPolicyBindingAbsentAndEmptyNamespace(t *testing.T) {
	for _, empty := range []bool{false, true} {
		root := writeMinimalSuite(t)
		if empty {
			if err := os.Mkdir(filepath.Join(root, "policies"), 0o755); err != nil {
				t.Fatal(err)
			}
		}
		for _, source := range policyBindingSources(t, root) {
			if _, err := ValidatePath(source); err != nil {
				t.Fatal(err)
			}
		}
		if bytes.Contains(policyBindingRead(t, root, "agents/writer.json"), []byte(`"policy"`)) {
			t.Fatal("nil policy was not omitted")
		}
	}
	for _, source := range policyBindingSources(t, filepath.Join("../../testdata", "coordinator-workers")) {
		if _, err := ValidatePath(source); err != nil {
			t.Fatalf("old fixture: %v", err)
		}
	}
	root := writeMinimalSuite(t)
	mustWrite(t, root, "policies/writer.json", []byte(bindingV1))
	assertPolicyBindingRejected(t, root, "orphaned")
}

func TestPolicyBindingDigestPropagationAndStaleAncestors(t *testing.T) {
	before, beforeRef := writePolicyBindingSuite(t, bindingMediaV1, []byte(bindingV1))
	after, afterRef := writePolicyBindingSuite(t, bindingMediaV1, []byte(bindingV1))
	addPolicyBindingUnchangedAgent(t, before)
	addPolicyBindingUnchangedAgent(t, after)
	changed := []byte(strings.Replace(bindingV1, `"/a"`, `"/b"`, 1))
	mustWrite(t, after, afterRef.Path, changed)
	assertPolicyBindingRejected(t, after, "policy document digest mismatch")
	afterRef.Descriptor = rawPolicyDescriptor(bindingMediaV1, changed)
	var agent map[string]any
	if err := json.Unmarshal(policyBindingRead(t, after, "agents/writer.json"), &agent); err != nil {
		t.Fatal(err)
	}
	agent["policy"] = afterRef
	mustWriteJSON(t, after, "agents/writer.json", MediaTypeAgent, agent)
	assertPolicyBindingRejected(t, after, "manifest digest mismatch")
	bindPolicyAgent(t, after, "writer", func(agent map[string]any) { agent["policy"] = afterRef })
	if beforeRef.Descriptor.Digest == afterRef.Descriptor.Digest {
		t.Fatal("policy identity unchanged")
	}
	var oldSuite, newSuite Suite
	if err := Unmarshal(policyBindingRead(t, before, "agentsuite.json"), &oldSuite); err != nil {
		t.Fatal(err)
	}
	if err := Unmarshal(policyBindingRead(t, after, "agentsuite.json"), &newSuite); err != nil {
		t.Fatal(err)
	}
	if oldSuite.Agents[0].Descriptor.Digest == newSuite.Agents[0].Descriptor.Digest {
		t.Fatal("Agent identity unchanged")
	}
	oldDigest, err := Digest(policyBindingRead(t, before, "agentsuite.json"))
	if err != nil {
		t.Fatal(err)
	}
	newDigest, err := Digest(policyBindingRead(t, after, "agentsuite.json"))
	if err != nil {
		t.Fatal(err)
	}
	if oldDigest == newDigest {
		t.Fatal("suite manifest identity unchanged")
	}
	for _, pair := range [][2]string{{before, after}, {writeTestOCILayout(t, before), writeTestOCILayout(t, after)}} {
		diff, err := DiffPaths(pair[0], pair[1])
		if err != nil {
			t.Fatal(err)
		}
		if diff.Before.ContentDigest == diff.After.ContentDigest {
			t.Fatal("content identity unchanged")
		}
		if diff.Before.SourceType != "directory" && (diff.Before.ArtifactDigest == "" || diff.Before.ArtifactDigest == diff.After.ArtifactDigest) {
			t.Fatal("OCI artifact identity unchanged")
		}
		if len(diff.AffectedAgents) != 1 || diff.AffectedAgents[0].ID != "writer" {
			t.Fatalf("wrong affected set: %+v", diff.AffectedAgents)
		}
		found := false
		for _, change := range diff.Changes {
			if change.Kind == "agent" && change.ID == "writer" {
				found = true
			}
		}
		if !found {
			t.Fatalf("missing Agent change: %+v", diff.Changes)
		}
	}
}

func TestPolicyBindingUsesOrdinaryNotEffectiveDigest(t *testing.T) {
	root, ref := writePolicyBindingSuite(t, bindingMediaV1, []byte(bindingV1))
	data := policyBindingRead(t, root, ref.Path)
	ordinary, err := Digest(data)
	if err != nil {
		t.Fatal(err)
	}
	if ref.Descriptor.Digest != ordinary {
		t.Fatal("descriptor is not ordinary JCS SHA-256")
	}
	suitePolicy, err := policy.DecodeSuitePolicy(data)
	if err != nil {
		t.Fatal(err)
	}
	effective, err := policy.Resolve(suitePolicy, policy.AdministrativePolicy{})
	if err != nil {
		t.Fatal(err)
	}
	effectiveBytes, err := policy.CanonicalBytes(effective)
	if err != nil {
		t.Fatal(err)
	}
	if bytes.Equal(data, effectiveBytes) {
		t.Fatal("test requires authored arrays differing from normalized effective sets")
	}
	if ordinary == policy.Digest(data) || ordinary == policy.Digest(effectiveBytes) {
		t.Fatal("ordinary and framed identities conflated")
	}
	ref.Descriptor.Digest = policy.Digest(data)
	bindPolicyAgent(t, root, "writer", func(agent map[string]any) { agent["policy"] = ref })
	assertPolicyBindingRejected(t, root, "digest mismatch")
}

func writePolicyBindingSuite(t *testing.T, media string, data []byte) (string, FileRef) {
	t.Helper()
	root := writeMinimalSuite(t)
	ref := FileRef{Path: "policies/writer.json", Descriptor: rawPolicyDescriptor(media, data)}
	mustWrite(t, root, ref.Path, data)
	bindPolicyAgent(t, root, "writer", func(agent map[string]any) { agent["policy"] = ref })
	return root, ref
}

func rawPolicyDescriptor(media string, data []byte) Descriptor {
	sum := sha256.Sum256(data)
	return Descriptor{MediaType: media, Digest: "sha256:" + hex.EncodeToString(sum[:]), Size: int64(len(data))}
}

func policyBindingRead(t *testing.T, root, name string) []byte {
	t.Helper()
	data, err := os.ReadFile(filepath.Join(root, name))
	if err != nil {
		t.Fatal(err)
	}
	return data
}

func bindPolicyAgent(t *testing.T, root, id string, mutate func(map[string]any)) {
	t.Helper()
	name := "agents/" + id + ".json"
	var agent map[string]any
	if err := json.Unmarshal(policyBindingRead(t, root, name), &agent); err != nil {
		t.Fatal(err)
	}
	mutate(agent)
	descriptor := mustWriteJSON(t, root, name, MediaTypeAgent, agent)
	var suite Suite
	if err := Unmarshal(policyBindingRead(t, root, "agentsuite.json"), &suite); err != nil {
		t.Fatal(err)
	}
	found := false
	for i := range suite.Agents {
		if suite.Agents[i].ID == id {
			suite.Agents[i].Descriptor = descriptor
			found = true
		}
	}
	if !found {
		t.Fatalf("missing Agent %s", id)
	}
	mustWriteJSON(t, root, "agentsuite.json", MediaTypeSuite, suite)
}

func assertPolicyBindingRejected(t *testing.T, root, want string) {
	t.Helper()
	for _, source := range policyBindingSources(t, root) {
		if _, err := ValidatePath(source); err == nil || !strings.Contains(err.Error(), want) {
			t.Fatalf("ValidatePath(%s) = %v, want %q", source, err, want)
		}
	}
}

func policyBindingSources(t *testing.T, root string) []string {
	t.Helper()
	// tarDirectory omits link targets; fill them so OCI checks exercise the
	// policy namespace, not the loader's unrelated empty-target rejection.
	input := tar.NewReader(bytes.NewReader(tarDirectory(t, root)))
	var buffer bytes.Buffer
	output := tar.NewWriter(&buffer)
	for {
		header, err := input.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			t.Fatal(err)
		}
		if header.Typeflag == tar.TypeSymlink {
			header.Linkname, err = os.Readlink(filepath.Join(root, header.Name))
			if err != nil {
				t.Fatal(err)
			}
		}
		if err := output.WriteHeader(header); err != nil {
			t.Fatal(err)
		}
		if _, err := io.Copy(output, input); err != nil {
			t.Fatal(err)
		}
	}
	if err := output.Close(); err != nil {
		t.Fatal(err)
	}
	return []string{root, writeTestOCILayoutTar(t, buffer.Bytes())}
}

func addPolicyBindingUnchangedAgent(t *testing.T, root string) {
	t.Helper()
	// Build the unrelated Agent from raw bytes without inheriting its policy.
	var raw map[string]any
	if err := json.Unmarshal(policyBindingRead(t, root, "agents/writer.json"), &raw); err != nil {
		t.Fatal(err)
	}
	raw["id"] = "observer"
	delete(raw, "policy")
	descriptor := mustWriteJSON(t, root, "agents/observer.json", MediaTypeAgent, raw)
	var composition Composition
	if err := Unmarshal(policyBindingRead(t, root, "compositions/writer-linux-amd64.json"), &composition); err != nil {
		t.Fatal(err)
	}
	composition.Agent = "observer"
	compositionDescriptor := mustWriteJSON(t, root, "compositions/observer-linux-amd64.json", MediaTypeComposition, composition)
	var suite Suite
	if err := Unmarshal(policyBindingRead(t, root, "agentsuite.json"), &suite); err != nil {
		t.Fatal(err)
	}
	suite.Agents = append(suite.Agents, ManifestRef{ID: "observer", Path: "agents/observer.json", Descriptor: descriptor})
	suite.Compositions = append(suite.Compositions, CompositionRef{Agent: "observer", Platform: composition.Platform, Path: "compositions/observer-linux-amd64.json", Descriptor: compositionDescriptor})
	mustWriteJSON(t, root, "agentsuite.json", MediaTypeSuite, suite)
}
