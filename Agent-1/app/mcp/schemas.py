from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MCPToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any]


class MCPToolCallRequest(BaseModel):
    tool_name: str = Field(..., description="Tool name")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments")


class MCPToolCallResponse(BaseModel):
    tool_name: str
    success: bool
    data: Any = None
    message: str = "ok"


class MCPIssueTokenRequest(BaseModel):
    patient_id: str
    hospital_id: Optional[str] = None
    expires_in_minutes: int = Field(default=120, ge=1, le=1440)


class MCPRecentMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    role: str = Field(..., description="user/assistant/system/tool")
    content: str = Field(..., description="Message content")


class MCPSessionState(BaseModel):
    model_config = ConfigDict(extra="ignore")

    intent: str = Field(default="", description="Current user intent")
    current_topic: str = Field(default="", description="Current topic")
    goal: str = Field(default="", description="Current goal")
    working_summary: str = Field(default="", description="Compact working-memory summary")
    next_action: str = Field(default="", description="Suggested next action for the current turn")
    memory_focus: str = Field(default="", description="Which memory scope should be trusted first")
    last_assistant_summary: str = Field(default="", description="Condensed summary of the last assistant reply")
    constraints: List[str] = Field(default_factory=list, description="Conversation constraints")
    confirmed_facts: List[str] = Field(default_factory=list, description="Confirmed facts")
    open_questions: List[str] = Field(default_factory=list, description="Open questions")
    identity_status: str = Field(default="unknown", description="unknown/pending_confirmation/confirmed/declined")
    claimed_name: Optional[str] = Field(default=None, description="User-stated name or nickname")
    claimed_birth_year: Optional[int] = Field(default=None, description="User-stated birth year")
    confirmed_patient_id: Optional[str] = Field(default=None, description="Resolved patient id")
    confirmed_patient_name: Optional[str] = Field(default=None, description="Resolved patient name")
    identity_source: Optional[str] = Field(default=None, description="How identity was resolved")
    identity_candidates: List[str] = Field(default_factory=list, description="Candidate patient ids when ambiguous")


class MCPActiveEntities(BaseModel):
    model_config = ConfigDict(extra="ignore")

    drugs: List[str] = Field(default_factory=list, description="Active drug entities")
    symptoms: List[str] = Field(default_factory=list, description="Active symptom entities")
    tests: List[str] = Field(default_factory=list, description="Active test entities")
    metrics: List[str] = Field(default_factory=list, description="Active metric entities")


class MCPRiskSignals(BaseModel):
    model_config = ConfigDict(extra="ignore")

    red_flags: List[str] = Field(default_factory=list, description="Red flag signals")
    medication_flags: List[str] = Field(default_factory=list, description="Medication-related flags")
    monitoring_flags: List[str] = Field(default_factory=list, description="Monitoring-related flags")


class MCPMemoryControl(BaseModel):
    model_config = ConfigDict(extra="ignore")

    recent_turn_limit: int = Field(default=5, ge=1, le=20)
    summary_token_budget: int = Field(default=300, ge=50, le=2000)
    compression_version: str = Field(default="v2")


class MCPShortTermMemory(BaseModel):
    model_config = ConfigDict(extra="ignore")

    recent_messages: List[MCPRecentMessage] = Field(default_factory=list)
    session_state: MCPSessionState = Field(default_factory=MCPSessionState)
    active_entities: MCPActiveEntities = Field(default_factory=MCPActiveEntities)
    risk_signals: MCPRiskSignals = Field(default_factory=MCPRiskSignals)

    @field_validator("risk_signals", mode="before")
    @classmethod
    def _coerce_risk_signals(cls, value):
        if isinstance(value, list):
            return {
                "red_flags": value,
                "medication_flags": [],
                "monitoring_flags": [],
            }
        if isinstance(value, dict):
            return value
        return value


class MCPAgentQueryRequest(BaseModel):
    question: str
    auth_token: Optional[str] = None
    patient_id: Optional[str] = None
    hospital_id: Optional[str] = None
    chat_mode: Optional[str] = Field(default=None, description="Chat mode: general or memory")
    claimed_name: Optional[str] = Field(default=None, description="User-stated name")
    claimed_phone: Optional[str] = Field(default=None, description="User-stated phone number")
    claimed_birth_year: Optional[int] = Field(default=None, description="User-stated birth year")
    session_id: Optional[str] = Field(default=None, description="Session ID")
    conversation_context: Optional[str] = Field(default=None, description="Short conversation context")
    short_term_memory: Optional[MCPShortTermMemory] = Field(default=None, description="Structured short-term memory")


class MCPAgentQueryResponse(BaseModel):
    question: str
    answer: str
    speech_text: Optional[str] = None
    image_analysis: Optional[str] = None
    intent: Optional[str] = None
    intent_confidence: Optional[float] = None
    planning_strategy: Optional[str] = None
    chosen_tool: str
    chosen_tools: List[str] = Field(default_factory=list)
    tool_arguments: Dict[str, Any]
    tool_result: Any
    execution_trace: Optional[List[Dict[str, Any]]] = None
    planning: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None
    patient_id: Optional[str] = None
    hospital_id: Optional[str] = None
    short_term_memory_count: Optional[int] = None
    short_term_memory: Optional[MCPShortTermMemory] = None
    memory_debug: Optional[Dict[str, Any]] = None
    answer_confidence: Optional[float] = Field(default=None, description="Answer confidence 0-1")
    confidence_reason: Optional[str] = Field(default=None, description="Confidence reason")


class MCPSpeechRequest(BaseModel):
    text: str = Field(..., description="Text to synthesize")
    voice: Optional[str] = Field(default=None, description="Voice name")
    response_format: str = Field(default="mp3", description="Output format")


class MCPSpeechResponse(BaseModel):
    text: str
    audio_base64: str
    mime_type: str
    voice: str
    model: str
    response_format: str


class MCPToolsResponse(BaseModel):
    tools: List[MCPToolDefinition]
