package artifact

import "github.com/agent-primitives/suite/core"

// Deprecated: use core.ExecutionHTTPV1.
const ExecutionHTTPV1 = core.ExecutionHTTPV1

// Deprecated: use core.AgentKitMountedConfig.
const AgentKitMountedConfig = core.AgentKitMountedConfig

// ExecutionContract is the portable core definition.
//
// Deprecated: use core.ExecutionContract.
type ExecutionContract = core.ExecutionContract

// ExecutionInput is the portable core definition.
//
// Deprecated: use core.ExecutionInput.
type ExecutionInput = core.ExecutionInput

// ValidateExecutionContract checks a portable execution declaration.
//
// Deprecated: use core.ValidateExecutionContract.
func ValidateExecutionContract(c ExecutionContract) error { return core.ValidateExecutionContract(c) }
