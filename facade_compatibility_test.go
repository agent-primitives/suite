package agentsuite_test

import (
	"errors"
	"io"
	"os/exec"
	"reflect"
	"strings"
	"testing"

	"github.com/agent-primitives/suite/core"
	"github.com/agent-primitives/suite/evidence"
	"github.com/agent-primitives/suite/experimental/flow"
	"github.com/agent-primitives/suite/internal/artifact"
	"github.com/agent-primitives/suite/oci"
)

func TestFacadeAliasIdentity(t *testing.T) {
	pairs := []struct {
		name                   string
		implementation, public reflect.Type
	}{
		{"AffectedAgent", reflect.TypeFor[artifact.AffectedAgent](), reflect.TypeFor[oci.AffectedAgent]()},
		{"DiffIdentity", reflect.TypeFor[artifact.DiffIdentity](), reflect.TypeFor[oci.DiffIdentity]()},
		{"DiffLimitError", reflect.TypeFor[artifact.DiffLimitError](), reflect.TypeFor[oci.DiffLimitError]()},
		{"DiffReport", reflect.TypeFor[artifact.DiffReport](), reflect.TypeFor[oci.DiffReport]()},
		{"DiffSummary", reflect.TypeFor[artifact.DiffSummary](), reflect.TypeFor[oci.DiffSummary]()},
		{"EvaluationEvidence", reflect.TypeFor[artifact.EvaluationEvidence](), reflect.TypeFor[evidence.EvaluationEvidence]()},
		{"EvidenceAssertionResult", reflect.TypeFor[artifact.EvidenceAssertionResult](), reflect.TypeFor[evidence.EvidenceAssertionResult]()},
		{"EvidenceCaseRef", reflect.TypeFor[artifact.EvidenceCaseRef](), reflect.TypeFor[evidence.EvidenceCaseRef]()},
		{"EvidenceCaseResult", reflect.TypeFor[artifact.EvidenceCaseResult](), reflect.TypeFor[evidence.EvidenceCaseResult]()},
		{"EvidenceDescriptor", reflect.TypeFor[artifact.EvidenceDescriptor](), reflect.TypeFor[evidence.EvidenceDescriptor]()},
		{"EvidenceEvaluation", reflect.TypeFor[artifact.EvidenceEvaluation](), reflect.TypeFor[evidence.EvidenceEvaluation]()},
		{"EvidenceEvaluator", reflect.TypeFor[artifact.EvidenceEvaluator](), reflect.TypeFor[evidence.EvidenceEvaluator]()},
		{"EvidenceEvaluatorIdentity", reflect.TypeFor[artifact.EvidenceEvaluatorIdentity](), reflect.TypeFor[evidence.EvidenceEvaluatorIdentity]()},
		{"EvidenceExecution", reflect.TypeFor[artifact.EvidenceExecution](), reflect.TypeFor[evidence.EvidenceExecution]()},
		{"EvidenceFileRef", reflect.TypeFor[artifact.EvidenceFileRef](), reflect.TypeFor[evidence.EvidenceFileRef]()},
		{"EvidenceImplementation", reflect.TypeFor[core.EvidenceImplementation](), reflect.TypeFor[evidence.EvidenceImplementation]()},
		{"EvidenceJudgeConfiguration", reflect.TypeFor[artifact.EvidenceJudgeConfiguration](), reflect.TypeFor[evidence.EvidenceJudgeConfiguration]()},
		{"EvidenceJudgeResult", reflect.TypeFor[artifact.EvidenceJudgeResult](), reflect.TypeFor[evidence.EvidenceJudgeResult]()},
		{"EvidenceModel", reflect.TypeFor[artifact.EvidenceModel](), reflect.TypeFor[evidence.EvidenceModel]()},
		{"EvidencePlatform", reflect.TypeFor[artifact.EvidencePlatform](), reflect.TypeFor[evidence.EvidencePlatform]()},
		{"EvidencePolicy", reflect.TypeFor[artifact.EvidencePolicy](), reflect.TypeFor[evidence.EvidencePolicy]()},
		{"EvidenceRefusal", reflect.TypeFor[artifact.EvidenceRefusal](), reflect.TypeFor[evidence.EvidenceRefusal]()},
		{"EvidenceRunResult", reflect.TypeFor[artifact.EvidenceRunResult](), reflect.TypeFor[evidence.EvidenceRunResult]()},
		{"EvidenceSubject", reflect.TypeFor[artifact.EvidenceSubject](), reflect.TypeFor[evidence.EvidenceSubject]()},
		{"ExpectedEvaluation", reflect.TypeFor[artifact.ExpectedEvaluation](), reflect.TypeFor[evidence.ExpectedEvaluation]()},
		{"FieldChange", reflect.TypeFor[artifact.FieldChange](), reflect.TypeFor[oci.FieldChange]()},
		{"FlowAssertionV1Alpha1", reflect.TypeFor[artifact.FlowAssertionV1Alpha1](), reflect.TypeFor[flow.FlowAssertionV1Alpha1]()},
		{"FlowCaseV1Alpha1", reflect.TypeFor[artifact.FlowCaseV1Alpha1](), reflect.TypeFor[flow.FlowCaseV1Alpha1]()},
		{"FlowEdgeRequirementV1Alpha1", reflect.TypeFor[artifact.FlowEdgeRequirementV1Alpha1](), reflect.TypeFor[flow.FlowEdgeRequirementV1Alpha1]()},
		{"FlowInputV1Alpha1", reflect.TypeFor[artifact.FlowInputV1Alpha1](), reflect.TypeFor[flow.FlowInputV1Alpha1]()},
		{"FlowStepV1Alpha1", reflect.TypeFor[artifact.FlowStepV1Alpha1](), reflect.TypeFor[flow.FlowStepV1Alpha1]()},
		{"FlowV1Alpha1", reflect.TypeFor[artifact.FlowV1Alpha1](), reflect.TypeFor[flow.FlowV1Alpha1]()},
		{"FlowV1Alpha1Graph", reflect.TypeFor[artifact.FlowV1Alpha1Graph](), reflect.TypeFor[flow.FlowV1Alpha1Graph]()},
		{"RecordChange", reflect.TypeFor[artifact.RecordChange](), reflect.TypeFor[oci.RecordChange]()},
		{"VerifiedEvaluation", reflect.TypeFor[artifact.VerifiedEvaluation](), reflect.TypeFor[evidence.VerifiedEvaluation]()},
	}
	for _, p := range pairs {
		if p.implementation != p.public {
			t.Errorf("%s: alias identity changed", p.name)
		}
	}
	if artifact.DiffAdded != oci.DiffAdded {
		t.Error("DiffAdded changed")
	}
	if artifact.DiffModified != oci.DiffModified {
		t.Error("DiffModified changed")
	}
	if artifact.DiffRemoved != oci.DiffRemoved {
		t.Error("DiffRemoved changed")
	}
	if artifact.DiffReportSchemaVersion != oci.DiffReportSchemaVersion {
		t.Error("DiffReportSchemaVersion changed")
	}
	if artifact.EvidenceJudgePolicyID != evidence.EvidenceJudgePolicyID {
		t.Error("EvidenceJudgePolicyID changed")
	}
	if artifact.EvidenceJudgePolicyVersion != evidence.EvidenceJudgePolicyVersion {
		t.Error("EvidenceJudgePolicyVersion changed")
	}
	if artifact.EvidencePolicyID != evidence.EvidencePolicyID {
		t.Error("EvidencePolicyID changed")
	}
	if artifact.EvidencePolicyVersion != evidence.EvidencePolicyVersion {
		t.Error("EvidencePolicyVersion changed")
	}
	if artifact.EvidenceSchemaVersion != evidence.EvidenceSchemaVersion {
		t.Error("EvidenceSchemaVersion changed")
	}
	if artifact.FlowExtensionV1Alpha1 != flow.FlowExtensionV1Alpha1 {
		t.Error("FlowExtensionV1Alpha1 changed")
	}
	if artifact.FlowPathV1Alpha1 != flow.FlowPathV1Alpha1 {
		t.Error("FlowPathV1Alpha1 changed")
	}
	if artifact.FlowVersionV1Alpha1 != flow.FlowVersionV1Alpha1 {
		t.Error("FlowVersionV1Alpha1 changed")
	}
	if artifact.MediaTypeEvaluationEvidence != evidence.MediaTypeEvaluationEvidence {
		t.Error("MediaTypeEvaluationEvidence changed")
	}
	var _ func(string) (*core.Report, error) = oci.ValidatePath
	var _ func(string) (*core.Report, error) = oci.ValidateDirectory
	var _ func(string, string) (oci.DiffReport, error) = oci.DiffPaths
	var _ func(string, evidence.ExpectedEvaluation, io.Reader) (*evidence.VerifiedEvaluation, error) = evidence.VerifyEvaluation
	var _ func(string, evidence.ExpectedEvaluation, io.Reader) (*evidence.VerifiedEvaluation, error) = evidence.VerifyEvaluationFlowV1Alpha1
	var _ func(string) (*flow.FlowV1Alpha1Graph, error) = flow.ValidatePathFlowV1Alpha1
	var _ func(string) (*flow.FlowV1Alpha1Graph, error) = flow.ValidateDirectoryFlowV1Alpha1
	var _ func() core.Report = (*flow.FlowV1Alpha1Graph)(nil).Report
	var _ func() flow.FlowV1Alpha1 = (*flow.FlowV1Alpha1Graph)(nil).Flow
}
func TestFacadeEvidenceRefusalIdentity(t *testing.T) {
	for _, verify := range []func(string, evidence.ExpectedEvaluation, io.Reader) (*evidence.VerifiedEvaluation, error){evidence.VerifyEvaluation, evidence.VerifyEvaluationFlowV1Alpha1} {
		_, err := verify("unused", evidence.ExpectedEvaluation{}, nil)
		var implementation *artifact.EvidenceRefusal
		var current *evidence.EvidenceRefusal
		if !errors.As(err, &implementation) || !errors.As(err, &current) || implementation != current || current.Code != "missing" {
			t.Fatalf("refusal identity/classification changed: %v", err)
		}
	}
}
func TestFacadeImplementationDependencies(t *testing.T) {
	for _, pkg := range []string{"internal/artifact", "oci", "evidence", "experimental/flow"} {
		t.Run(pkg, func(t *testing.T) {
			command := exec.Command("go", "list", "-deps", "github.com/agent-primitives/suite/"+pkg)
			output, err := command.CombinedOutput()
			if err != nil {
				t.Fatalf("dependencies: %v\n%s", err, output)
			}
			for _, dep := range strings.Fields(string(output)) {
				if dep == "github.com/agent-primitives/suite" {
					t.Errorf("focused API/engine imports root: %s", dep)
				}
				if pkg == "internal/artifact" && (dep == "github.com/agent-primitives/suite/oci" || dep == "github.com/agent-primitives/suite/evidence" || strings.HasPrefix(dep, "github.com/agent-primitives/suite/experimental/")) {
					t.Errorf("engine imports public facade: %s", dep)
				}
			}
		})
	}
}
