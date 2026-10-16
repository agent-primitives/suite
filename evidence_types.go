package agentsuite

const (
	MediaTypeEvaluationEvidence = "application/vnd.agentsuite.eval.evidence.v1+json"
	EvidenceSchemaVersion       = "1.0.0"
	// EvidencePolicyID names text contains/notContains/RE2 semantics, all-known
	// assertion conjunction and the unknown veto, including non-critical checks.
	EvidencePolicyID      = "agentsuite-text-v1"
	EvidencePolicyVersion = "1.0.0"
	// EvidenceJudgePolicyID requires exactly two independent scores: both at or
	// above minScore pass, both below fail, and a split remains unknown.
	EvidenceJudgePolicyID      = "agentsuite-double-score-v1"
	EvidenceJudgePolicyVersion = "1.0.0"
)

// EvaluationEvidence is an unsigned, payload-free claim about one evaluation.
// Decoding validates the closed wire shape, not execution or a full pass.
// VerifyEvaluation additionally checks independently supplied expectations and
// the local OCI artifact. No prompts, answers or arbitrary metadata belong here.
type EvaluationEvidence struct {
	SchemaVersion string               `json:"schemaVersion"`
	MediaType     string               `json:"mediaType"`
	Subject       EvidenceSubject      `json:"subject"`
	Execution     EvidenceExecution    `json:"execution"`
	Evaluation    EvidenceEvaluation   `json:"evaluation"`
	Evaluator     EvidenceEvaluator    `json:"evaluator"`
	Results       []EvidenceCaseResult `json:"results"`
}

// EvidenceDescriptor deliberately excludes OCI annotations and remote locations.
// The manifest descriptor hashes raw bytes; index/case descriptors use JCS.
type EvidenceDescriptor struct {
	MediaType string `json:"mediaType"`
	Digest    string `json:"digest"`
	Size      int64  `json:"size"`
}

type EvidencePlatform struct {
	OS           string `json:"os"`
	Architecture string `json:"architecture"`
	Variant      string `json:"variant"`
}

type EvidenceSubject struct {
	Manifest           EvidenceDescriptor `json:"manifest"`
	MemberID           string             `json:"memberID"`
	MemberDigest       string             `json:"memberDigest"`
	CompositionDigest  string             `json:"compositionDigest"`
	BuildProfileDigest string             `json:"buildProfileDigest"`
	Platform           EvidencePlatform   `json:"platform"`
}

type EvidenceImplementation struct {
	ID      string `json:"id"`
	Version string `json:"version"`
	Digest  string `json:"digest"`
}

type EvidenceModel struct {
	Protocol            string `json:"protocol"`
	ID                  string `json:"id"`
	ConfigurationDigest string `json:"configurationDigest"`
}

// EvidenceExecution distinguishes runtime/harness implementations, model
// inference settings and the renderer/execution profile. Configuration digests
// must hash documented non-secret projections, never credentials or endpoints.
type EvidenceExecution struct {
	Runtime             EvidenceImplementation `json:"runtime"`
	Model               EvidenceModel          `json:"model"`
	Harness             EvidenceImplementation `json:"harness"`
	Renderer            EvidenceImplementation `json:"renderer"`
	Profile             EvidenceImplementation `json:"profile"`
	ConfigurationDigest string                 `json:"configurationDigest"`
}

type EvidencePolicy struct {
	ID                  string `json:"id"`
	Version             string `json:"version"`
	ConfigurationDigest string `json:"configurationDigest"`
}

type EvidenceEvaluatorIdentity struct {
	ID      string         `json:"id"`
	Version string         `json:"version"`
	Policy  EvidencePolicy `json:"policy"`
}

type EvidenceEvaluator struct {
	Identity    EvidenceEvaluatorIdentity `json:"identity"`
	StartedAt   string                    `json:"startedAt"`
	CompletedAt string                    `json:"completedAt"`
}

type EvidenceFileRef struct {
	Path       string             `json:"path"`
	Descriptor EvidenceDescriptor `json:"descriptor"`
}

type EvidenceCaseRef struct {
	ID         string             `json:"id"`
	Path       string             `json:"path"`
	Descriptor EvidenceDescriptor `json:"descriptor"`
	Runs       int                `json:"runs"`
	MinPasses  int                `json:"minPasses"`
}

type EvidenceEvaluation struct {
	Index EvidenceFileRef   `json:"index"`
	Cases []EvidenceCaseRef `json:"cases"`
}

type EvidenceCaseResult struct {
	ID      string              `json:"id"`
	Outcome string              `json:"outcome"`
	Runs    []EvidenceRunResult `json:"runs"`
}

type EvidenceRunResult struct {
	Number     int                       `json:"number"`
	Status     string                    `json:"status"`
	Outcome    string                    `json:"outcome"`
	Assertions []EvidenceAssertionResult `json:"assertions"`
}

type EvidenceAssertionResult struct {
	ID      string               `json:"id"`
	Type    string               `json:"type"`
	Outcome string               `json:"outcome"`
	Judge   *EvidenceJudgeResult `json:"judge,omitempty"`
}

// EvidenceJudgeConfiguration names authored model/version requirements and an
// independently accepted judge policy and non-secret configuration projection.
type EvidenceJudgeConfiguration struct {
	Model   string         `json:"model"`
	Version string         `json:"version"`
	Policy  EvidencePolicy `json:"policy"`
}

// EvidenceJudgeResult keeps authored configuration distinct from declared
// observed response model identities. Neither identity is attested. Each
// observed model must exactly equal model or model + "-" + version. Scores and
// observedModels are either both empty (unavailable) or both length two.
// Producers must initialize empty slices rather than leave them nil: JSON null
// is malformed; non-null empty arrays represent an unavailable observation.
type EvidenceJudgeResult struct {
	Configuration  EvidenceJudgeConfiguration `json:"configuration"`
	ObservedModels []string                   `json:"observedModels"`
	Scores         []int                      `json:"scores"`
	MinScore       int                        `json:"minScore"`
}

// ExpectedEvaluation must be resolved independently, never copied from claims.
// All subject/execution/evaluator fields are required; Judges is an explicit
// allowlist of complete configurations, empty only when no judge is accepted.
// Evaluation times are deliberately not caller expectations.
type ExpectedEvaluation struct {
	Subject   EvidenceSubject              `json:"subject"`
	Execution EvidenceExecution            `json:"execution"`
	Evaluator EvidenceEvaluatorIdentity    `json:"evaluator"`
	Judges    []EvidenceJudgeConfiguration `json:"judges"`
}

// VerifiedEvaluation summarizes consistency, not authenticity, truth, freshness
// or deployment readiness. It contains no raw unverified evidence inputs.
type VerifiedEvaluation struct {
	Subject     EvidenceSubject `json:"subject"`
	Cases       int             `json:"cases"`
	Runs        int             `json:"runs"`
	CompletedAt string          `json:"completedAt"`
	Unsigned    bool            `json:"unsigned"`
}

// EvidenceRefusal exposes a stable code without untrusted text or wrapped causes.
// Codes: missing, malformed, unsupported, limit, artifact, subject, coverage,
// policy, unknown, not-passing.
type EvidenceRefusal struct{ Code string }

func (e *EvidenceRefusal) Error() string {
	if e != nil {
		switch e.Code {
		case "missing", "malformed", "unsupported", "limit", "artifact", "subject", "coverage", "policy", "unknown", "not-passing":
			return "evaluation evidence refused: " + e.Code
		}
	}
	return "evaluation evidence refused"
}

func evidenceRefuse(code string) error { return &EvidenceRefusal{Code: code} }
