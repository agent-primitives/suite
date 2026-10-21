package artifact

import (
	"errors"
	"slices"
	"strings"
)

// FlowV1Alpha1Graph is an explicitly selected experimental graph. Validation
// establishes stored definitions, not execution, approval or a whole-suite pass.
// Its accessors return caller-owned copies of the verified inventory.
type FlowV1Alpha1Graph struct {
	flow   FlowV1Alpha1
	digest string
	report Report
}

// ValidatePathFlowV1Alpha1 selects only the kmx.flow.v1alpha1 contract on an
// extracted directory or OCI layout. It never retries the default reader or
// rewrites the original artifact to remove a required extension.
func ValidatePathFlowV1Alpha1(path string) (*FlowV1Alpha1Graph, error) {
	content, err := loadPathContent(path)
	if err != nil {
		return nil, err
	}
	return validateFlowContentV1Alpha1(content)
}

// ValidateDirectoryFlowV1Alpha1 validates an extracted flow graph without OCI
// auto-detection, preserving the ordinary directory loader's safety boundary.
func ValidateDirectoryFlowV1Alpha1(root string) (*FlowV1Alpha1Graph, error) {
	content, err := loadDirectory(root)
	if err != nil {
		return nil, err
	}
	return validateFlowContentV1Alpha1(content)
}

func validateFlowContentV1Alpha1(content *contentSet) (*FlowV1Alpha1Graph, error) {
	v, report, err := validateContentGraphMode(content, true)
	if err != nil {
		return nil, err
	}
	return &FlowV1Alpha1Graph{flow: *v.flow, digest: v.flowDigest, report: *report}, nil
}

// FlowDigest is the digest bound by the original suite's critical selector.
func (g *FlowV1Alpha1Graph) FlowDigest() string { return g.digest }

// Flow returns copied definitions, including pointer-valued run policies.
func (g *FlowV1Alpha1Graph) Flow() FlowV1Alpha1 {
	f := g.flow
	f.EdgeRequirements = slices.Clone(f.EdgeRequirements)
	f.Steps = slices.Clone(f.Steps)
	f.Cases = slices.Clone(f.Cases)
	for i := range f.Cases {
		c := &f.Cases[i]
		if c.Runs != nil {
			n := *c.Runs
			c.Runs = &n
		}
		if c.MinPasses != nil {
			n := *c.MinPasses
			c.MinPasses = &n
		}
		c.Assertions = slices.Clone(c.Assertions)
		for j := range c.Assertions {
			a := &c.Assertions[j].Check
			if a.Critical != nil {
				b := *a.Critical
				a.Critical = &b
			}
		}
	}
	return f
}

// Report returns the ordinary core inventory, not runtime readiness.
func (g *FlowV1Alpha1Graph) Report() Report {
	r := g.report
	r.Capabilities = slices.Clone(r.Capabilities)
	r.CompositionSelections = slices.Clone(r.CompositionSelections)
	r.AgentPlatforms = slices.Clone(r.AgentPlatforms)
	for i := range r.AgentPlatforms {
		r.AgentPlatforms[i].Platforms = slices.Clone(r.AgentPlatforms[i].Platforms)
	}
	return r
}

func validateFlowExtensionsV1Alpha1(extensions []Extension) error {
	if err := validateExtensionsMode(extensions, true); err != nil {
		return err
	}
	for _, e := range extensions {
		if e.Name == FlowExtensionV1Alpha1 {
			if e.Critical && IsValidDigest(e.Digest) {
				return nil
			}
			return errors.New("flow requires a critical selector with a SHA-256 digest")
		}
	}
	return errors.New("experimental flow selector is missing")
}

func (v *validator) validateFlowV1Alpha1() error {
	for name, entry := range v.content.entries {
		if name != "coordination" && !strings.HasPrefix(name, "coordination/") {
			continue
		}
		if name == "coordination" && entry.Type == "directory" {
			continue
		}
		if name != FlowPathV1Alpha1 || entry.Type != "file" {
			return errors.New("flow content closure contains an unsupported entry")
		}
	}
	raw, err := v.content.data(FlowPathV1Alpha1)
	if err != nil || len(raw) > maxJSONBytes {
		return errors.New("flow document is missing or exceeds its limit")
	}
	var digest string
	for _, e := range v.suite.Extensions {
		if e.Name == FlowExtensionV1Alpha1 {
			digest = e.Digest
		}
	}
	// Reject raw mismatch cheaply, then apply strict JSON implementation limits
	// before canonicalization, as evaluationDocument does for core evaluations.
	descriptor := Descriptor{Digest: digest, Size: int64(len(raw))}
	if !descriptorSizeAndDigestMatch(raw, descriptor) {
		return errors.New("flow document digest or canonical storage mismatch")
	}
	flow, err := decodeFlowV1Alpha1(raw)
	if err != nil {
		return err
	}
	if !matchesCanonicalDescriptor(raw, descriptor) {
		return errors.New("flow document digest or canonical storage mismatch")
	}
	for _, step := range flow.Steps {
		if _, ok := v.agents[step.Member]; !ok {
			return errors.New("flow step references an unknown member")
		}
	}
	for _, edge := range flow.EdgeRequirements {
		a, ok := v.agents[edge.From]
		if !ok {
			return errors.New("flow edge source is unknown")
		}
		declared := false
		for _, invoke := range a.Invokes {
			if invoke.Agent == edge.To {
				declared = true
				break
			}
		}
		if !declared {
			return errors.New("flow requirement references an undeclared invocation edge")
		}
	}
	if err := v.validateFlowBoundsV1Alpha1(flow); err != nil {
		return err
	}
	v.flow, v.flowDigest = &flow, digest
	return nil
}

func (v *validator) validateFlowBoundsV1Alpha1(flow FlowV1Alpha1) error {
	cases, runs, rows := 0, 0, 0
	add := func(policy *int, assertions int) error {
		n := 1
		if policy != nil {
			n = *policy
		}
		cases++
		if cases > maxEvaluationCases || n < 1 || n > maxEvidenceRunsPerCase || n > maxEvidenceRuns-runs || assertions > (maxEvidenceRows-rows)/n {
			return errors.New("combined member and flow evaluation inventory exceeds limits")
		}
		runs += n
		rows += n * assertions
		return nil
	}
	for _, c := range flow.Cases {
		if err := add(c.Runs, len(c.Assertions)); err != nil {
			return err
		}
	}
	// Core validation already checked this immutable, descriptor-bound inventory.
	for _, agent := range v.agents {
		for _, ref := range agent.Evals {
			data, err := v.content.data(ref.Path)
			if err != nil {
				return err
			}
			var index EvaluationIndex
			if err := decodeStrict(data, &index); err != nil {
				return err
			}
			for _, ref := range index.Cases {
				data, err := v.content.data(ref.Path)
				if err != nil {
					return err
				}
				var c EvaluationCase
				if err := decodeStrict(data, &c); err != nil {
					return err
				}
				if err := add(c.Runs, len(c.Assertions)); err != nil {
					return err
				}
			}
		}
	}
	return nil
}
