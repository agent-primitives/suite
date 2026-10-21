package agentsuite

import (
	"encoding/json"
	"errors"
	"regexp"
	"strings"
	"time"

	"github.com/agent-primitives/suite/internal/contract"
)

const (
	maxEvidenceRunsPerCase = 1000
	maxEvidenceRuns        = 4096
	maxEvidenceRows        = 32000
)

var (
	evidenceTimePattern = regexp.MustCompile(`^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,9})?Z$`)
)

// UnmarshalJSON adds required-presence checks to the package's existing strict
// JSON decoder. This is a fixed evidence shape, not an extensible schema engine.
func (e *EvaluationEvidence) UnmarshalJSON(data []byte) error {
	if len(data) > maxJSONBytes {
		return evidenceRefuse("limit")
	}
	type plain EvaluationEvidence
	var value plain
	if err := Unmarshal(data, &value); err != nil {
		if errors.Is(err, errJSONMemberLimit) || errors.Is(err, errJSONDepthLimit) {
			return evidenceRefuse("limit")
		}
		return evidenceRefuse("malformed")
	}
	if err := evidenceShape(data, "root"); err != nil {
		return err
	}
	if err := validateEvidence(EvaluationEvidence(value)); err != nil {
		return err
	}
	*e = EvaluationEvidence(value)
	return nil
}

func evidenceShape(data []byte, kind string) error {
	required := ""
	children := map[string]string{}
	arrays := map[string]string{}
	switch kind {
	case "root":
		required = "schemaVersion mediaType subject execution evaluation evaluator results"
		children = map[string]string{"subject": "subject", "execution": "execution", "evaluation": "evaluation", "evaluator": "evaluator"}
		arrays["results"] = "caseResult"
	case "subject":
		required = "manifest memberID memberDigest compositionDigest buildProfileDigest platform"
		children = map[string]string{"manifest": "descriptor", "platform": "platform"}
	case "descriptor":
		required = "mediaType digest size"
	case "platform":
		required = "os architecture variant"
	case "execution":
		required = "runtime model harness renderer profile configurationDigest"
		children = map[string]string{"runtime": "implementation", "model": "model", "harness": "implementation", "renderer": "implementation", "profile": "implementation"}
	case "implementation":
		required = "id version digest"
	case "model":
		required = "protocol id configurationDigest"
	case "policy":
		required = "id version configurationDigest"
	case "evaluatorIdentity":
		required = "id version policy"
		children["policy"] = "policy"
	case "evaluator":
		required = "identity startedAt completedAt"
		children["identity"] = "evaluatorIdentity"
	case "evaluation":
		required = "index cases"
		children["index"] = "fileRef"
		arrays["cases"] = "caseRef"
	case "fileRef":
		required = "path descriptor"
		children["descriptor"] = "descriptor"
	case "caseRef":
		required = "id path descriptor runs minPasses"
		children["descriptor"] = "descriptor"
	case "caseResult":
		required = "id outcome runs"
		arrays["runs"] = "run"
	case "run":
		required = "number status outcome assertions"
		arrays["assertions"] = "assertion"
	case "assertion":
		required = "id type outcome"
		children["judge"] = "judge"
	case "judge":
		required = "configuration observedModels scores minScore"
		children["configuration"] = "judgeConfiguration"
	case "judgeConfiguration":
		required = "model version policy"
		children["policy"] = "policy"
	}
	fields, code := contract.RequiredObject(data, required)
	if code != "" {
		return evidenceRefuse(code)
	}
	for key, child := range children {
		if value, ok := fields[key]; ok {
			if err := evidenceShape(value, child); err != nil {
				return err
			}
		}
	}
	for key, child := range arrays {
		var values []json.RawMessage
		if err := json.Unmarshal(fields[key], &values); err != nil {
			return evidenceRefuse("malformed")
		}
		for _, value := range values {
			if err := evidenceShape(value, child); err != nil {
				return err
			}
		}
	}
	return nil
}

func evidenceToken(value string) bool { return contract.EvidenceToken(value) }
func evidenceImplementation(v EvidenceImplementation) bool {
	return contract.EvidenceImplementation(v.ID, v.Version, v.Digest)
}
func evidencePolicy(v EvidencePolicy) bool {
	return evidenceToken(v.ID) && evidenceToken(v.Version) && IsValidDigest(v.ConfigurationDigest)
}
func evidenceSubject(v EvidenceSubject) bool {
	return v.Manifest.MediaType == ociManifestMediaType && IsValidDigest(v.Manifest.Digest) && v.Manifest.Size > 0 && v.Manifest.Size <= maxJSONBytes &&
		evidenceToken(v.MemberID) && IsValidDigest(v.MemberDigest) && IsValidDigest(v.CompositionDigest) && IsValidDigest(v.BuildProfileDigest) &&
		evidenceToken(v.Platform.OS) && evidenceToken(v.Platform.Architecture) && (v.Platform.Variant == "" || evidenceToken(v.Platform.Variant))
}
func evidenceExecution(v EvidenceExecution) bool {
	return evidenceImplementation(v.Runtime) && evidenceImplementation(v.Harness) && evidenceImplementation(v.Renderer) && evidenceImplementation(v.Profile) &&
		evidenceToken(v.Model.Protocol) && evidenceToken(v.Model.ID) && IsValidDigest(v.Model.ConfigurationDigest) && IsValidDigest(v.ConfigurationDigest)
}
func evidenceEvaluator(v EvidenceEvaluatorIdentity) bool {
	return evidenceToken(v.ID) && evidenceToken(v.Version) && evidencePolicy(v.Policy)
}
func evidenceJudgeConfiguration(v EvidenceJudgeConfiguration) bool {
	return evidenceToken(v.Model) && evidenceToken(v.Version) && evidencePolicy(v.Policy)
}
func evidenceOutcome(v string) bool { return v == "pass" || v == "fail" || v == "unknown" }
func evidenceDescriptor(v EvidenceDescriptor, mediaType string) bool {
	return v.MediaType == mediaType && IsValidDigest(v.Digest) && v.Size > 0 && v.Size <= maxJSONBytes
}
func evidencePath(value string, casePath bool) bool {
	parts := strings.Split(value, "/")
	if len(parts) == 3 && !casePath {
		return parts[0] == "evals" && evidenceToken(parts[1]) && parts[2] == "index.json"
	}
	if len(parts) == 4 && casePath {
		return parts[0] == "evals" && evidenceToken(parts[1]) && parts[2] == "cases" && strings.HasSuffix(parts[3], ".json") && evidenceToken(strings.TrimSuffix(parts[3], ".json"))
	}
	return false
}

func validateEvidence(e EvaluationEvidence) error {
	if e.SchemaVersion != EvidenceSchemaVersion || e.MediaType != MediaTypeEvaluationEvidence {
		return evidenceRefuse("unsupported")
	}
	if !evidenceSubject(e.Subject) || !evidenceExecution(e.Execution) || !evidenceEvaluator(e.Evaluator.Identity) {
		return evidenceRefuse("malformed")
	}
	start, err := time.Parse(time.RFC3339Nano, e.Evaluator.StartedAt)
	end, endErr := time.Parse(time.RFC3339Nano, e.Evaluator.CompletedAt)
	if err != nil || endErr != nil || !evidenceTimePattern.MatchString(e.Evaluator.StartedAt) || !evidenceTimePattern.MatchString(e.Evaluator.CompletedAt) || start.After(end) {
		return evidenceRefuse("malformed")
	}
	if !evidencePath(e.Evaluation.Index.Path, false) || !evidenceDescriptor(e.Evaluation.Index.Descriptor, MediaTypeEvaluationIndex) {
		return evidenceRefuse("malformed")
	}
	if len(e.Evaluation.Cases) > maxEvaluationCases || len(e.Results) > maxEvaluationCases {
		return evidenceRefuse("limit")
	}
	for _, c := range e.Evaluation.Cases {
		if !evaluationIDPattern.MatchString(c.ID) || !evidenceToken(c.ID) || !evidencePath(c.Path, true) || !evidenceDescriptor(c.Descriptor, MediaTypeEvaluationCase) || c.Runs < 1 || c.MinPasses < 1 {
			return evidenceRefuse("malformed")
		}
		if c.Runs > maxEvidenceRunsPerCase || c.MinPasses > maxEvidenceRunsPerCase {
			return evidenceRefuse("limit")
		}
	}
	runs, rows := 0, 0
	for _, c := range e.Results {
		if !evaluationIDPattern.MatchString(c.ID) || !evidenceToken(c.ID) || !evidenceOutcome(c.Outcome) {
			return evidenceRefuse("malformed")
		}
		if len(c.Runs) > maxEvidenceRunsPerCase || len(c.Runs) > maxEvidenceRuns-runs {
			return evidenceRefuse("limit")
		}
		runs += len(c.Runs)
		for _, run := range c.Runs {
			if run.Number < 1 || !evidenceOutcome(run.Outcome) {
				return evidenceRefuse("malformed")
			}
			if run.Number > maxEvidenceRunsPerCase {
				return evidenceRefuse("limit")
			}
			switch run.Status {
			case "completed", "error", "cancelled", "unknown":
			default:
				return evidenceRefuse("malformed")
			}
			if len(run.Assertions) > maxEvaluationAssertions || len(run.Assertions) > maxEvidenceRows-rows {
				return evidenceRefuse("limit")
			}
			rows += len(run.Assertions)
			for _, a := range run.Assertions {
				if !evaluationIDPattern.MatchString(a.ID) || !evidenceToken(a.ID) || !evidenceToken(a.Type) || !evidenceOutcome(a.Outcome) {
					return evidenceRefuse("malformed")
				}
				if a.Judge == nil {
					continue
				}
				j := a.Judge
				if a.Type != "llmJudge" || !evidenceJudgeConfiguration(j.Configuration) || j.MinScore < 0 || j.MinScore > 100 || (len(j.Scores) != 0 && len(j.Scores) != 2) || len(j.ObservedModels) != len(j.Scores) {
					return evidenceRefuse("malformed")
				}
				for i, score := range j.Scores {
					if score < 0 || score > 100 || !evidenceToken(j.ObservedModels[i]) {
						return evidenceRefuse("malformed")
					}
				}
			}
		}
	}
	return nil
}
