package artifact

import (
	"path/filepath"
	"testing"
)

func TestRuntimeProfilesSameOCISeparateEvidence(t *testing.T) {
	root, suite, profiles := runtimeProfileSuite(t)
	layout := writeTestOCILayout(t, root)
	var index ociIndex
	readStrictJSON(t, filepath.Join(layout, "index.json"), &index)
	manifest := index.Manifests[0]
	_, _, template := evidenceFixture(t, nil)
	var claims [2]EvaluationEvidence
	var expectations [2]ExpectedEvaluation
	for i := range profiles {
		p := profiles[i]
		e := template
		e.Subject.Manifest = EvidenceDescriptor{MediaType: manifest.MediaType, Digest: manifest.Digest, Size: manifest.Size}
		e.Subject.MemberDigest = suite.Agents[0].Descriptor.Digest
		e.Subject.CompositionDigest = suite.Compositions[i].Descriptor.Digest
		e.Subject.BuildProfileDigest = suite.BuildProfiles[0].Descriptor.Digest
		e.Execution.Runtime, e.Execution.Harness, e.Execution.Renderer = p.Runtime, p.Harness, p.Renderer
		e.Execution.Profile = EvidenceImplementation{ID: p.ID, Version: SpecVersion, Digest: suite.RuntimeProfiles[i].Descriptor.Digest}
		// Producer/caller projection includes image identity. Verifier only sees
		// its digest, not the preimage or an authenticated image receipt.
		e.Execution.ConfigurationDigest = digestBytes(mustJSON(t, map[string]string{
			"configurationABI": p.ConfigurationABI,
			"imageDigest":      digestBytes([]byte(p.ID + " synthetic final image")),
		}))
		expected := ExpectedEvaluation{Subject: e.Subject, Execution: e.Execution, Evaluator: e.Evaluator.Identity}
		claims[i], expectations[i] = e, expected
		evidenceCode(t, layout, expected, evidenceBytes(t, e), "")
	}
	if claims[0].Subject.Manifest != claims[1].Subject.Manifest || claims[0].Evaluation.Index != claims[1].Evaluation.Index {
		t.Fatal("passes must bind the exact same OCI manifest and authored evaluation")
	}
	for _, name := range []string{"runtime", "harness", "renderer", "profile", "configuration", "subject", "joint-execution-relabel"} {
		t.Run(name, func(t *testing.T) {
			e, expected := claims[0], expectations[0]
			switch name {
			case "runtime":
				e.Execution.Runtime = claims[1].Execution.Runtime
			case "harness":
				e.Execution.Harness = claims[1].Execution.Harness
			case "renderer":
				e.Execution.Renderer = claims[1].Execution.Renderer
			case "profile":
				e.Execution.Profile = claims[1].Execution.Profile
			case "configuration":
				e.Execution.ConfigurationDigest = claims[1].Execution.ConfigurationDigest
			case "subject":
				e.Subject = claims[1].Subject // independent expectations stay fixed
			case "joint-execution-relabel":
				e.Execution = claims[1].Execution
				expected.Execution = e.Execution // source composition stays fixed
			}
			evidenceCode(t, layout, expected, evidenceBytes(t, e), "subject")
		})
	}
	// Even self-consistent alterations to each pinned identity are refused by
	// the artifact; a caller configuration digest itself remains opaque.
	for _, name := range []string{"runtime", "harness", "renderer", "profile-id", "profile-version", "profile-digest"} {
		t.Run("joint-"+name, func(t *testing.T) {
			e, expected := claims[0], expectations[0]
			switch name {
			case "runtime":
				e.Execution.Runtime.Digest = digestBytes(nil)
			case "harness":
				e.Execution.Harness.Digest = digestBytes(nil)
			case "renderer":
				e.Execution.Renderer.Digest = digestBytes(nil)
			case "profile-id":
				e.Execution.Profile.ID = "other"
			case "profile-version":
				e.Execution.Profile.Version = "2.0.0"
			case "profile-digest":
				e.Execution.Profile.Digest = digestBytes(nil)
			}
			expected.Execution = e.Execution
			evidenceCode(t, layout, expected, evidenceBytes(t, e), "subject")
		})
	}
	// One profile change repackages S: neither old detached pass binds new S,
	// including the pass for the otherwise unchanged profile/composition.
	profiles[1].ImageRequired = false
	suite.RuntimeProfiles[1].Descriptor = mustWriteJSON(t, root, suite.RuntimeProfiles[1].Path, MediaTypeRuntimeProfile, profiles[1])
	mustWriteJSON(t, root, "agentsuite.json", MediaTypeSuite, suite)
	changedLayout := writeTestOCILayout(t, root)
	readStrictJSON(t, filepath.Join(changedLayout, "index.json"), &index)
	if index.Manifests[0].Digest == manifest.Digest {
		t.Fatal("profile change did not change S")
	}
	for i := range claims {
		evidenceCode(t, changedLayout, expectations[i], evidenceBytes(t, claims[i]), "subject")
	}
}
