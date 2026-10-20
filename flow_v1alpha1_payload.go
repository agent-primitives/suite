package agentsuite

import (
	"encoding/json"
	"errors"
	"strings"
)

const (
	FlowVersionV1Alpha1   = "kmx.flow/v1alpha1"
	FlowExtensionV1Alpha1 = "kmx.flow.v1alpha1"
	FlowPathV1Alpha1      = "coordination/flow.json"
)

// FlowV1Alpha1 is the closed experimental serial-flow payload. It carries no
// graph validation authority; membership and invokes references need the graph.
type FlowV1Alpha1 struct {
	SchemaVersion    string                        `json:"schemaVersion"`
	ID               string                        `json:"id"`
	Mode             string                        `json:"mode"`
	Entry            string                        `json:"entry"`
	EdgeRequirements []FlowEdgeRequirementV1Alpha1 `json:"edgeRequirements"`
	Steps            []FlowStepV1Alpha1            `json:"steps"`
	Cases            []FlowCaseV1Alpha1            `json:"cases"`
}

type FlowEdgeRequirementV1Alpha1 struct {
	From     string `json:"from"`
	To       string `json:"to"`
	Approval string `json:"approval"`
}

type FlowStepV1Alpha1 struct {
	ID       string            `json:"id"`
	Member   string            `json:"member"`
	Input    FlowInputV1Alpha1 `json:"input"`
	Approval string            `json:"approval,omitempty"`
}

type FlowInputV1Alpha1 struct {
	Source  string `json:"source"`
	Context string `json:"context,omitempty"`
}

type FlowCaseV1Alpha1 struct {
	ID         string                  `json:"id"`
	Input      string                  `json:"input"`
	Runs       *int                    `json:"runs,omitempty"`
	MinPasses  *int                    `json:"minPasses,omitempty"`
	Assertions []FlowAssertionV1Alpha1 `json:"assertions"`
}

type FlowAssertionV1Alpha1 struct {
	Step  string              `json:"step"`
	Check EvaluationAssertion `json:"check"`
}

func decodeFlowV1Alpha1(raw []byte) (FlowV1Alpha1, error) {
	refuse := func(message string) (FlowV1Alpha1, error) {
		return FlowV1Alpha1{}, errors.New(message)
	}
	var flow FlowV1Alpha1
	// Do not expose parser errors: unknown names and malformed operands may
	// contain private source paths or other author-controlled content.
	if len(raw) > maxJSONBytes || decodeStrict(raw, &flow) != nil {
		return refuse("flow JSON is invalid")
	}
	fields, err := flowPayloadFields(raw, "schemaVersion", "id", "mode", "entry", "edgeRequirements", "steps", "cases")
	if err != nil {
		return refuse("flow requires non-null fields")
	}
	if flow.SchemaVersion != FlowVersionV1Alpha1 || flow.Mode != "pipeline" ||
		!identifierPattern.MatchString(flow.ID) || !identifierPattern.MatchString(flow.Entry) {
		return refuse("flow version, mode, id or entry is invalid")
	}
	approvalValid := func(value string) bool { return value == "required" || value == "policy-controlled" }
	if _, err := flowPayloadObjects(fields["edgeRequirements"], "from", "to", "approval"); err != nil {
		return refuse("flow edge requirement requires non-null fields")
	}
	seenEdges := map[[2]string]bool{}
	for _, edge := range flow.EdgeRequirements {
		key := [2]string{edge.From, edge.To}
		if !identifierPattern.MatchString(edge.From) || !identifierPattern.MatchString(edge.To) ||
			!approvalValid(edge.Approval) || seenEdges[key] {
			return refuse("flow edge requirement is invalid or duplicated")
		}
		seenEdges[key] = true
	}
	steps, err := flowPayloadObjects(fields["steps"], "id", "member", "input")
	if err != nil || len(flow.Steps) != 2 {
		return refuse("flow requires exactly two complete steps")
	}
	stepIDs := map[string]bool{}
	sources := map[string]bool{"run.input": true}
	for i, step := range flow.Steps {
		input, err := flowPayloadFields(steps[i]["input"], "source")
		if err != nil {
			return refuse("flow step input requires non-null fields")
		}
		_, hasApproval := steps[i]["approval"]
		_, hasContext := input["context"]
		if !evaluationIDPattern.MatchString(step.ID) || stepIDs[step.ID] || !identifierPattern.MatchString(step.Member) ||
			hasApproval && !approvalValid(step.Approval) || hasContext && step.Input.Context != "run.input" {
			return refuse("flow step id, member, approval or context is invalid")
		}
		if !sources[step.Input.Source] || i == 0 && (step.Member != flow.Entry || step.Input.Source != "run.input") {
			return refuse("flow step requires run input or an earlier step output")
		}
		stepIDs[step.ID] = true
		sources[step.ID+".output"] = true
	}
	cases, err := flowPayloadObjects(fields["cases"], "id", "input", "assertions")
	if err != nil || len(flow.Cases) < 1 || len(flow.Cases) > maxEvaluationCases {
		return refuse("flow requires 1..128 complete cases")
	}
	caseIDs := map[string]bool{}
	totalRuns, totalRows := 0, 0
	for i, c := range flow.Cases {
		if !evaluationIDPattern.MatchString(c.ID) || caseIDs[c.ID] || strings.TrimSpace(c.Input) == "" ||
			len(c.Assertions) < 1 || len(c.Assertions) > maxEvaluationAssertions {
			return refuse("flow case requires a unique id, nonblank input and 1..1000 assertions")
		}
		caseIDs[c.ID] = true
		runs := 1
		if c.Runs != nil {
			runs = *c.Runs
		}
		if runs < 1 || runs > maxEvidenceRunsPerCase ||
			c.MinPasses != nil && (c.Runs == nil || *c.MinPasses < 1 || *c.MinPasses > runs) {
			return refuse("flow case run policy is invalid")
		}
		// Check before multiplication; these are local budgets only. Graph
		// validation also accounts for every member's cases and observations.
		if runs > maxEvidenceRuns-totalRuns || runs > (maxEvidenceRows-totalRows)/len(c.Assertions) {
			return refuse("flow exceeds run or assertion row limits")
		}
		totalRuns += runs
		totalRows += runs * len(c.Assertions)
		assertions, err := flowPayloadObjects(cases[i]["assertions"], "step", "check")
		if err != nil {
			return refuse("flow assertion requires non-null step and check")
		}
		checkIDs := map[string]bool{}
		for j, a := range c.Assertions {
			if !stepIDs[a.Step] || !evaluationIDPattern.MatchString(a.Check.ID) || checkIDs[a.Check.ID] {
				return refuse("flow assertion step or check id is invalid or duplicated")
			}
			checkIDs[a.Check.ID] = true
			switch a.Check.Type {
			case "contains", "notContains", "regex":
			default:
				return refuse("flow assertion type is unsupported")
			}
			if err := validateEvaluationAssertion(a.Check, assertions[j]["check"]); err != nil {
				return refuse("flow assertion check is invalid")
			}
		}
	}
	return flow, nil
}

// Typed strict decoding rejects unknown/duplicate fields but cannot distinguish
// an absent string from an authored empty string, or null from omitted pointers.
// Inspect raw presence locally rather than broadening the frozen core codec.
func flowPayloadFields(raw []byte, required ...string) (map[string]json.RawMessage, error) {
	var fields map[string]json.RawMessage
	if err := json.Unmarshal(raw, &fields); err != nil || fields == nil {
		return nil, errors.New("flow object is invalid")
	}
	for _, field := range required {
		if _, ok := fields[field]; !ok {
			return nil, errors.New("flow object is missing a required field")
		}
	}
	for _, value := range fields {
		if strings.TrimSpace(string(value)) == "null" {
			return nil, errors.New("flow field must not be null")
		}
	}
	return fields, nil
}

func flowPayloadObjects(raw []byte, required ...string) ([]map[string]json.RawMessage, error) {
	var items []json.RawMessage
	if err := json.Unmarshal(raw, &items); err != nil || items == nil {
		return nil, errors.New("flow array is invalid")
	}
	objects := make([]map[string]json.RawMessage, len(items))
	for i, item := range items {
		fields, err := flowPayloadFields(item, required...)
		if err != nil {
			return nil, err
		}
		objects[i] = fields
	}
	return objects, nil
}
