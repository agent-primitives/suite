package core

type Report struct {
	Name                     string                 `json:"name"`
	Agents                   int                    `json:"agents"`
	ToolProviders            int                    `json:"toolProviders"`
	ToolProviderCompositions int                    `json:"toolProviderCompositions"`
	Compositions             int                    `json:"compositions"`
	Capabilities             []string               `json:"capabilities"`
	AgentPlatforms           []AgentPlatform        `json:"agentPlatforms"`
	CompositionSelections    []CompositionSelection `json:"compositionSelections"`
}

type CompositionSelection struct {
	RuntimeProfile string   `json:"runtimeProfile,omitempty"`
	Agent          string   `json:"agent"`
	Platform       Platform `json:"platform"`
	BuildProfile   string   `json:"buildProfile"`
	Digest         string   `json:"digest"`
}
