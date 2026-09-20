export type EvidenceTier =
  | 'CALIBRATED'
  | 'LIMITED'
  | 'PRIOR_ONLY'
  | 'PROXY_ONLY'
  | 'NON_IDENTIFIABLE'
  | 'ASSOCIATIONAL'
  | 'UNKNOWN';

export interface Race {
  race_id: string;
  season_id?: string | null;
  round?: number | null;
  circuit_id?: string | null;
  race_date?: string | null;
  total_laps?: number | null;
  availability: string;
  unavailable: string[];
}

export interface RaceDetail extends Race {
  circuit_name?: string | null;
  driver_count?: number | null;
  evidence_tiers?: Record<string, string> | null;
}

export interface RaceSimulationRequest {
  race_id: string;
  seed?: number | null;
  laps_override?: number | null;
  track_id?: string | null;
  enable_strategy: boolean;
  enable_setup: boolean;
  enable_weather: boolean;
  enable_race_control: boolean;
  save_replay?: boolean;
}

export interface MonteCarloRequest {
  race_id: string;
  simulations: number;
  seed?: number | null;
  laps_override?: number | null;
  enable_strategy?: boolean;
  enable_setup?: boolean;
  enable_weather?: boolean;
  enable_race_control?: boolean;
  save_replay?: boolean;
}

export interface JobStatus {
  simulation_id: string;
  job_id?: string | null;
  status: string;
  simulation_type?: string | null;
  request_hash?: string | null;
  progress?: number | null;
  current_stage?: string | null;
  poll_url?: string | null;
}

export interface SingleRaceResult extends JobStatus {
  race_id: string;
  seed?: number | null;
  track_id?: string | null;
  total_laps?: number | null;
  classification?: Array<Record<string, unknown>> | null;
  lap_summary?: Record<string, unknown> | null;
  provenance?: Record<string, unknown> | null;
  evidence_tiers?: Record<string, string> | null;
  warnings?: string[];
  reproducibility?: Record<string, unknown> | null;
}

export interface MonteCarloResult extends JobStatus {
  race_id: string;
  seed?: number | null;
  N?: number | null;
  simulations?: number | null;
  win_probabilities?: Record<string, number> | null;
  podium_probabilities?: Record<string, number> | null;
  finish_position_distribution?: Record<string, Record<string, number>> | null;
  expected_points?: Record<string, number> | null;
  provenance?: Record<string, unknown> | null;
  evidence_tiers?: Record<string, string> | null;
  warnings?: string[];
}

export interface MetadataResponse {
  dataset_version: string;
  dataset_hash: string;
  calibration_version: string;
  tyre_version: string;
  weather_version: string;
  race_control_version: string;
  strategy_version: string;
  setup_version: string;
  race_engine_version: string;
  model_version: string;
  simulation_version: string;
  evidence_tiers: Record<string, string>;
  provenance: Record<string, unknown>;
}

export interface ApiError {
  error: { code: string; message: string; details?: unknown };
}
