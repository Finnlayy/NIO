from enum import Enum, auto

class SystemExecutionState(Enum):
    PLANNING = auto()
    DISPATCHED = auto()
    RUNNING = auto()
    REFLECTING = auto()
    COMPLETE = auto()

class TrancheLifecycleState(Enum):
    T1 = auto()
    T2 = auto()
    T3 = auto()
    FREE_ROLL = auto()

class FeedConnectionState(Enum):
    CONNECTED_LIVE = auto()
    STALE_CACHE_DEGRADED = auto()

class MarketRegimeState(Enum):
    DECOUPLED_META = auto()
    BTC_SATELLITE = auto()
    ETH_EVM_SATELLITE = auto()
    CHOP_REACTIVE_NOISE = auto()

# Transition rules aligned with Phase 2 Reflection Planning
TRANSITION_MAP = {
    SystemExecutionState.PLANNING: {
        "allowed_next": [SystemExecutionState.DISPATCHED, SystemExecutionState.COMPLETE],
        "triggers": ["plan_approved", "plan_rejected"],
        "guard": lambda state: state.get("plan_approved", False) or state.get("plan_rejected", False),
    },
    SystemExecutionState.DISPATCHED: {
        "allowed_next": [SystemExecutionState.RUNNING, SystemExecutionState.COMPLETE],
        "triggers": ["execution_started", "execution_cancelled"],
        "guard": lambda state: state.get("execution_started", False) or state.get("execution_cancelled", False),
    },
    SystemExecutionState.RUNNING: {
        "allowed_next": [SystemExecutionState.REFLECTING, SystemExecutionState.COMPLETE],
        "triggers": ["execution_complete", "post_mortem_triggered", "timeout", "safety_net_activated"],
        "guard": lambda state: (
            state.get("execution_complete", False)
            or state.get("post_mortem_triggered", False)
            or state.get("timeout", False)
            or state.get("safety_net_activated", False)
        ),
    },
    SystemExecutionState.REFLECTING: {
        "allowed_next": [SystemExecutionState.COMPLETE, SystemExecutionState.PLANNING],
        "triggers": ["reflection_complete", "reflection_failed", "plan_revised"],
        "guard": lambda state: (
            state.get("reflection_complete", False)
            or state.get("reflection_failed", False)
            or state.get("plan_revised", False)
        ),
    },
    SystemExecutionState.COMPLETE: {
        "allowed_next": [SystemExecutionState.PLANNING],
        "triggers": ["new_plan_approved", "loop_requested"],
        "guard": lambda state: state.get("new_plan_approved", False) or state.get("loop_requested", False),
    },
}

# Guard conditions referencing blueprint concepts (Phase 2 alignment)
GUARD_CONDITIONS = {
    "plan_approved": lambda state: state.get("confidence_score", 0.0) >= 0.7,
    "execution_started": lambda state: state.get("feed_live", False) is True,
    "post_mortem_triggered": lambda state: (
        state.get("verdict") == "rejected"
        or len(state.get("errors", [])) > 0
        or state.get("timeout", False)
        or state.get("safety_net_activated", False)
    ),
    "reflection_complete": lambda state: state.get("reflection_result") is not None,
    "new_plan_approved": lambda state: state.get("revised_plan_approved", False) is True,
}
