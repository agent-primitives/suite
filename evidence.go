package agentsuite

import (
	"io"
)

// VerifyEvaluation checks one unsigned evidence document against independently
// resolved expectations and a genuine local OCI layout. It performs no network
// access or execution. A successful result proves only internal consistency of
// claims: it does not authenticate the evaluator, observations, or clock.
// Reader, path, JSON and authored-content errors are never included in refusals.
func VerifyEvaluation(layoutPath string, expected ExpectedEvaluation, evidenceReader io.Reader) (*VerifiedEvaluation, error) {
	if !evidenceSubject(expected.Subject) || !evidenceExecution(expected.Execution) || !evidenceEvaluator(expected.Evaluator) {
		return nil, evidenceRefuse("missing")
	}
	if expected.Evaluator.Policy.ID != EvidencePolicyID || expected.Evaluator.Policy.Version != EvidencePolicyVersion {
		return nil, evidenceRefuse("unsupported")
	}
	if len(expected.Judges) > maxEvaluationCases*maxEvaluationAssertions {
		return nil, evidenceRefuse("limit")
	}
	accepted := make(map[EvidenceJudgeConfiguration]bool, len(expected.Judges))
	for _, j := range expected.Judges {
		if !evidenceJudgeConfiguration(j) {
			return nil, evidenceRefuse("missing")
		}
		if j.Policy.ID != EvidenceJudgePolicyID || j.Policy.Version != EvidenceJudgePolicyVersion {
			return nil, evidenceRefuse("unsupported")
		}
		if accepted[j] {
			return nil, evidenceRefuse("policy")
		}
		accepted[j] = true
	}
	if evidenceReader == nil {
		return nil, evidenceRefuse("missing")
	}
	data, err := io.ReadAll(io.LimitReader(evidenceReader, maxJSONBytes+1))
	if len(data) > maxJSONBytes {
		return nil, evidenceRefuse("limit")
	}
	if err != nil {
		return nil, evidenceRefuse("malformed")
	}
	if len(data) == 0 {
		return nil, evidenceRefuse("missing")
	}
	var e EvaluationEvidence
	if err := e.UnmarshalJSON(data); err != nil {
		return nil, err
	}
	if e.Subject != expected.Subject || e.Execution != expected.Execution {
		return nil, evidenceRefuse("subject")
	}
	if e.Evaluator.Identity.Policy.ID != EvidencePolicyID || e.Evaluator.Identity.Policy.Version != EvidencePolicyVersion {
		return nil, evidenceRefuse("unsupported")
	}
	if e.Evaluator.Identity != expected.Evaluator {
		return nil, evidenceRefuse("policy")
	}
	content, err := loadOCILayoutContent(layoutPath)
	if err != nil {
		return nil, evidenceRefuse("artifact")
	}
	if content.artifactDigest != e.Subject.Manifest.Digest {
		return nil, evidenceRefuse("subject")
	}
	// The loader checked the index's exact manifest bytes. Re-read with the full
	// claimed descriptor to bind size as well, without canonicalizing the manifest.
	manifest := e.Subject.Manifest
	if _, err := readBlob(layoutPath, ociDescriptor{MediaType: manifest.MediaType, Digest: manifest.Digest, Size: manifest.Size}); err != nil {
		return nil, evidenceRefuse("subject")
	}
	v, _, err := validateContentGraph(content)
	if err != nil {
		return nil, evidenceRefuse("artifact")
	}
	agent, ok := v.agents[e.Subject.MemberID]
	if !ok {
		return nil, evidenceRefuse("subject")
	}
	memberMatched, compositionMatched, buildMatched := false, false, false
	for _, ref := range v.suite.Agents {
		if ref.ID == agent.ID && ref.Descriptor.Digest == e.Subject.MemberDigest {
			memberMatched = true
		}
	}
	platform := Platform{OS: e.Subject.Platform.OS, Architecture: e.Subject.Platform.Architecture, Variant: e.Subject.Platform.Variant}
	composition, ok := v.compositions[agent.ID+"@"+platform.String()]
	if !ok {
		return nil, evidenceRefuse("subject")
	}
	for _, ref := range v.suite.Compositions {
		if ref.Agent == agent.ID && ref.Platform == platform && ref.Descriptor.Digest == e.Subject.CompositionDigest {
			compositionMatched = true
		}
	}
	for _, ref := range v.suite.BuildProfiles {
		if ref.ID == composition.BuildProfile && ref.Descriptor.Digest == e.Subject.BuildProfileDigest {
			buildMatched = true
		}
	}
	if !memberMatched || !compositionMatched || !buildMatched {
		return nil, evidenceRefuse("subject")
	}
	if agent.Model.Protocol != e.Execution.Model.Protocol || agent.Model.Model != e.Execution.Model.ID {
		return nil, evidenceRefuse("subject")
	}
	if len(agent.Evals) != 1 {
		return nil, evidenceRefuse("missing")
	}
	indexRef := agent.Evals[0]
	if !evidenceRefMatches(e.Evaluation.Index, indexRef) {
		return nil, evidenceRefuse("coverage")
	}
	var index EvaluationIndex
	if _, err := v.evaluationDocument(indexRef, MediaTypeEvaluationIndex, &index); err != nil {
		return nil, evidenceRefuse("artifact")
	}
	if len(index.Cases) == 0 || len(index.Cases) != len(e.Evaluation.Cases) || len(index.Cases) != len(e.Results) {
		return nil, evidenceRefuse("coverage")
	}
	totalRuns, totalRows, notPassing := 0, 0, false
	for i, ref := range index.Cases {
		var c EvaluationCase
		if _, err := v.evaluationDocument(ref, MediaTypeEvaluationCase, &c); err != nil {
			return nil, evidenceRefuse("artifact")
		}
		runs, minPasses := 1, 1
		if c.Runs != nil {
			runs = *c.Runs
			minPasses = runs
		}
		if c.MinPasses != nil {
			minPasses = *c.MinPasses
		}
		// Bound authored counts before multiplication or iteration, even if the
		// document omits the corresponding rows. Never truncate oversized cases.
		if runs > maxEvidenceRunsPerCase || runs > maxEvidenceRuns-totalRuns || runs > (maxEvidenceRows-totalRows)/len(c.Assertions) {
			return nil, evidenceRefuse("limit")
		}
		totalRuns += runs
		totalRows += runs * len(c.Assertions)
		claim := e.Evaluation.Cases[i]
		if claim.ID != c.ID || claim.Runs != runs || claim.MinPasses != minPasses || !evidenceRefMatches(EvidenceFileRef{Path: claim.Path, Descriptor: claim.Descriptor}, ref) {
			return nil, evidenceRefuse("coverage")
		}
		row := e.Results[i]
		if row.ID != c.ID || len(row.Runs) != runs {
			return nil, evidenceRefuse("coverage")
		}
		passes := 0
		for n, run := range row.Runs {
			if run.Number != n+1 || len(run.Assertions) != len(c.Assertions) {
				return nil, evidenceRefuse("coverage")
			}
			if run.Status != "completed" {
				return nil, evidenceRefuse("unknown")
			}
			runOutcome := "pass"
			for j, assertion := range c.Assertions {
				observation := run.Assertions[j]
				if observation.ID != assertion.ID || observation.Type != assertion.Type {
					return nil, evidenceRefuse("coverage")
				}
				outcome, err := verifyEvidenceAssertion(assertion, observation, accepted)
				if err != nil {
					return nil, err
				}
				if outcome == "fail" {
					runOutcome = "fail"
				}
			}
			if run.Outcome == "unknown" {
				return nil, evidenceRefuse("unknown")
			}
			if run.Outcome != runOutcome {
				return nil, evidenceRefuse("policy")
			}
			if runOutcome == "pass" {
				passes++
			}
		}
		caseOutcome := "pass"
		if passes < minPasses {
			caseOutcome = "fail"
			notPassing = true
		}
		if row.Outcome == "unknown" {
			return nil, evidenceRefuse("unknown")
		}
		if row.Outcome != caseOutcome {
			return nil, evidenceRefuse("policy")
		}
	}
	if notPassing {
		return nil, evidenceRefuse("not-passing")
	}
	return &VerifiedEvaluation{Subject: expected.Subject, Cases: len(index.Cases), Runs: totalRuns, CompletedAt: e.Evaluator.CompletedAt, Unsigned: true}, nil
}

func evidenceRefMatches(claim EvidenceFileRef, ref FileRef) bool {
	return claim.Path == ref.Path && claim.Descriptor == (EvidenceDescriptor{MediaType: ref.Descriptor.MediaType, Digest: ref.Descriptor.Digest, Size: ref.Descriptor.Size})
}

func verifyEvidenceAssertion(authored EvaluationAssertion, row EvidenceAssertionResult, accepted map[EvidenceJudgeConfiguration]bool) (string, error) {
	switch authored.Type {
	case "contains", "notContains", "regex":
		if row.Judge != nil {
			return "", evidenceRefuse("policy")
		}
	case "llmJudge":
		if row.Judge == nil {
			return "", evidenceRefuse("coverage")
		}
		j := row.Judge
		if j.Configuration.Policy.ID != EvidenceJudgePolicyID || j.Configuration.Policy.Version != EvidenceJudgePolicyVersion {
			return "", evidenceRefuse("unsupported")
		}
		if !accepted[j.Configuration] || j.Configuration.Model != authored.JudgeModel || j.Configuration.Version != authored.JudgeVersion || j.MinScore != *authored.MinScore {
			return "", evidenceRefuse("policy")
		}
		if len(j.Scores) != 2 {
			return "", evidenceRefuse("unknown")
		}
		for _, model := range j.ObservedModels {
			if model != authored.JudgeModel && model != authored.JudgeModel+"-"+authored.JudgeVersion {
				return "", evidenceRefuse("policy")
			}
		}
		first, second := j.Scores[0] >= j.MinScore, j.Scores[1] >= j.MinScore
		if first != second {
			return "", evidenceRefuse("unknown")
		}
		outcome := "fail"
		if first {
			outcome = "pass"
		}
		if row.Outcome == "unknown" {
			return "", evidenceRefuse("unknown")
		}
		if row.Outcome != outcome {
			return "", evidenceRefuse("policy")
		}
	case "toolCalled", "toolNotCalled":
		return "", evidenceRefuse("unsupported")
	default:
		return "", evidenceRefuse("unknown")
	}
	if row.Outcome == "unknown" {
		return "", evidenceRefuse("unknown")
	}
	return row.Outcome, nil
}
