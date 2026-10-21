package agentsuite_test

import (
	"errors"
	"io"
	"os/exec"
	"reflect"
	"strings"
	"testing"

	agentsuite "github.com/agent-primitives/suite"
	"github.com/agent-primitives/suite/core"
	"github.com/agent-primitives/suite/evidence"
	"github.com/agent-primitives/suite/experimental/flow"
	"github.com/agent-primitives/suite/oci"
)

func TestFacadeCompatibilityTypes(t *testing.T) {
	pairs := []struct {
		name     string
		old, new reflect.Type
	}{
		{"AffectedAgent", reflect.TypeFor[agentsuite.AffectedAgent](), reflect.TypeFor[oci.AffectedAgent]()},
		{"DiffIdentity", reflect.TypeFor[agentsuite.DiffIdentity](), reflect.TypeFor[oci.DiffIdentity]()},
		{"DiffLimitError", reflect.TypeFor[agentsuite.DiffLimitError](), reflect.TypeFor[oci.DiffLimitError]()},
		{"DiffReport", reflect.TypeFor[agentsuite.DiffReport](), reflect.TypeFor[oci.DiffReport]()},
		{"DiffSummary", reflect.TypeFor[agentsuite.DiffSummary](), reflect.TypeFor[oci.DiffSummary]()},
		{"EvaluationEvidence", reflect.TypeFor[agentsuite.EvaluationEvidence](), reflect.TypeFor[evidence.EvaluationEvidence]()},
		{"EvidenceAssertionResult", reflect.TypeFor[agentsuite.EvidenceAssertionResult](), reflect.TypeFor[evidence.EvidenceAssertionResult]()},
		{"EvidenceCaseRef", reflect.TypeFor[agentsuite.EvidenceCaseRef](), reflect.TypeFor[evidence.EvidenceCaseRef]()},
		{"EvidenceCaseResult", reflect.TypeFor[agentsuite.EvidenceCaseResult](), reflect.TypeFor[evidence.EvidenceCaseResult]()},
		{"EvidenceDescriptor", reflect.TypeFor[agentsuite.EvidenceDescriptor](), reflect.TypeFor[evidence.EvidenceDescriptor]()},
		{"EvidenceEvaluation", reflect.TypeFor[agentsuite.EvidenceEvaluation](), reflect.TypeFor[evidence.EvidenceEvaluation]()},
		{"EvidenceEvaluator", reflect.TypeFor[agentsuite.EvidenceEvaluator](), reflect.TypeFor[evidence.EvidenceEvaluator]()},
		{"EvidenceEvaluatorIdentity", reflect.TypeFor[agentsuite.EvidenceEvaluatorIdentity](), reflect.TypeFor[evidence.EvidenceEvaluatorIdentity]()},
		{"EvidenceExecution", reflect.TypeFor[agentsuite.EvidenceExecution](), reflect.TypeFor[evidence.EvidenceExecution]()},
		{"EvidenceFileRef", reflect.TypeFor[agentsuite.EvidenceFileRef](), reflect.TypeFor[evidence.EvidenceFileRef]()},
		{"EvidenceImplementation", reflect.TypeFor[agentsuite.EvidenceImplementation](), reflect.TypeFor[evidence.EvidenceImplementation]()},
		{"EvidenceJudgeConfiguration", reflect.TypeFor[agentsuite.EvidenceJudgeConfiguration](), reflect.TypeFor[evidence.EvidenceJudgeConfiguration]()},
		{"EvidenceJudgeResult", reflect.TypeFor[agentsuite.EvidenceJudgeResult](), reflect.TypeFor[evidence.EvidenceJudgeResult]()},
		{"EvidenceModel", reflect.TypeFor[agentsuite.EvidenceModel](), reflect.TypeFor[evidence.EvidenceModel]()},
		{"EvidencePlatform", reflect.TypeFor[agentsuite.EvidencePlatform](), reflect.TypeFor[evidence.EvidencePlatform]()},
		{"EvidencePolicy", reflect.TypeFor[agentsuite.EvidencePolicy](), reflect.TypeFor[evidence.EvidencePolicy]()},
		{"EvidenceRefusal", reflect.TypeFor[agentsuite.EvidenceRefusal](), reflect.TypeFor[evidence.EvidenceRefusal]()},
		{"EvidenceRunResult", reflect.TypeFor[agentsuite.EvidenceRunResult](), reflect.TypeFor[evidence.EvidenceRunResult]()},
		{"EvidenceSubject", reflect.TypeFor[agentsuite.EvidenceSubject](), reflect.TypeFor[evidence.EvidenceSubject]()},
		{"ExpectedEvaluation", reflect.TypeFor[agentsuite.ExpectedEvaluation](), reflect.TypeFor[evidence.ExpectedEvaluation]()},
		{"FieldChange", reflect.TypeFor[agentsuite.FieldChange](), reflect.TypeFor[oci.FieldChange]()},
		{"FlowAssertionV1Alpha1", reflect.TypeFor[agentsuite.FlowAssertionV1Alpha1](), reflect.TypeFor[flow.FlowAssertionV1Alpha1]()},
		{"FlowCaseV1Alpha1", reflect.TypeFor[agentsuite.FlowCaseV1Alpha1](), reflect.TypeFor[flow.FlowCaseV1Alpha1]()},
		{"FlowEdgeRequirementV1Alpha1", reflect.TypeFor[agentsuite.FlowEdgeRequirementV1Alpha1](), reflect.TypeFor[flow.FlowEdgeRequirementV1Alpha1]()},
		{"FlowInputV1Alpha1", reflect.TypeFor[agentsuite.FlowInputV1Alpha1](), reflect.TypeFor[flow.FlowInputV1Alpha1]()},
		{"FlowStepV1Alpha1", reflect.TypeFor[agentsuite.FlowStepV1Alpha1](), reflect.TypeFor[flow.FlowStepV1Alpha1]()},
		{"FlowV1Alpha1", reflect.TypeFor[agentsuite.FlowV1Alpha1](), reflect.TypeFor[flow.FlowV1Alpha1]()},
		{"FlowV1Alpha1Graph", reflect.TypeFor[agentsuite.FlowV1Alpha1Graph](), reflect.TypeFor[flow.FlowV1Alpha1Graph]()},
		{"RecordChange", reflect.TypeFor[agentsuite.RecordChange](), reflect.TypeFor[oci.RecordChange]()},
		{"VerifiedEvaluation", reflect.TypeFor[agentsuite.VerifiedEvaluation](), reflect.TypeFor[evidence.VerifiedEvaluation]()},
	}
	for _, p := range pairs {
		if p.old != p.new {
			t.Errorf("%s: alias identity changed", p.name)
		}
	}
	if agentsuite.DiffAdded != oci.DiffAdded {
		t.Error("DiffAdded changed")
	}
	if agentsuite.DiffModified != oci.DiffModified {
		t.Error("DiffModified changed")
	}
	if agentsuite.DiffRemoved != oci.DiffRemoved {
		t.Error("DiffRemoved changed")
	}
	if agentsuite.DiffReportSchemaVersion != oci.DiffReportSchemaVersion {
		t.Error("DiffReportSchemaVersion changed")
	}
	if agentsuite.EvidenceJudgePolicyID != evidence.EvidenceJudgePolicyID {
		t.Error("EvidenceJudgePolicyID changed")
	}
	if agentsuite.EvidenceJudgePolicyVersion != evidence.EvidenceJudgePolicyVersion {
		t.Error("EvidenceJudgePolicyVersion changed")
	}
	if agentsuite.EvidencePolicyID != evidence.EvidencePolicyID {
		t.Error("EvidencePolicyID changed")
	}
	if agentsuite.EvidencePolicyVersion != evidence.EvidencePolicyVersion {
		t.Error("EvidencePolicyVersion changed")
	}
	if agentsuite.EvidenceSchemaVersion != evidence.EvidenceSchemaVersion {
		t.Error("EvidenceSchemaVersion changed")
	}
	if agentsuite.FlowExtensionV1Alpha1 != flow.FlowExtensionV1Alpha1 {
		t.Error("FlowExtensionV1Alpha1 changed")
	}
	if agentsuite.FlowPathV1Alpha1 != flow.FlowPathV1Alpha1 {
		t.Error("FlowPathV1Alpha1 changed")
	}
	if agentsuite.FlowVersionV1Alpha1 != flow.FlowVersionV1Alpha1 {
		t.Error("FlowVersionV1Alpha1 changed")
	}
	if agentsuite.MediaTypeEvaluationEvidence != evidence.MediaTypeEvaluationEvidence {
		t.Error("MediaTypeEvaluationEvidence changed")
	}
	var _ func(string) (*core.Report, error) = oci.ValidatePath
	var _ func(string) (*core.Report, error) = oci.ValidateDirectory
	var _ func(string, string) (agentsuite.DiffReport, error) = oci.DiffPaths
	var _ func(string, agentsuite.ExpectedEvaluation, io.Reader) (*agentsuite.VerifiedEvaluation, error) = evidence.VerifyEvaluation
	var _ func(string, agentsuite.ExpectedEvaluation, io.Reader) (*agentsuite.VerifiedEvaluation, error) = evidence.VerifyEvaluationFlowV1Alpha1
	var _ func(string) (*agentsuite.FlowV1Alpha1Graph, error) = flow.ValidatePathFlowV1Alpha1
	var _ func(string) (*agentsuite.FlowV1Alpha1Graph, error) = flow.ValidateDirectoryFlowV1Alpha1
	var _ func() core.Report = (*flow.FlowV1Alpha1Graph)(nil).Report
	var _ func() flow.FlowV1Alpha1 = (*flow.FlowV1Alpha1Graph)(nil).Flow
}
func TestFacadeEvidenceRefusalIdentity(t *testing.T) {
	for _, verify := range []func(string, evidence.ExpectedEvaluation, io.Reader) (*evidence.VerifiedEvaluation, error){agentsuite.VerifyEvaluation, evidence.VerifyEvaluation, agentsuite.VerifyEvaluationFlowV1Alpha1, evidence.VerifyEvaluationFlowV1Alpha1} {
		_, err := verify("unused", evidence.ExpectedEvaluation{}, nil)
		var old *agentsuite.EvidenceRefusal
		var current *evidence.EvidenceRefusal
		if !errors.As(err, &old) || !errors.As(err, &current) || old != current || current.Code != "missing" {
			t.Fatalf("refusal identity/classification changed: %v", err)
		}
	}
}
func TestFacadeImplementationDependencies(t *testing.T) {
	command := exec.Command("go", "list", "-deps", "github.com/agent-primitives/suite/internal/artifact")
	output, err := command.CombinedOutput()
	if err != nil {
		t.Fatalf("engine imports: %v\n%s", err, output)
	}
	for _, dep := range strings.Fields(string(output)) {
		if dep == "github.com/agent-primitives/suite" || dep == "github.com/agent-primitives/suite/oci" || dep == "github.com/agent-primitives/suite/evidence" || strings.HasPrefix(dep, "github.com/agent-primitives/suite/experimental/") {
			t.Errorf("engine imports public facade/root: %s", dep)
		}
	}
}
