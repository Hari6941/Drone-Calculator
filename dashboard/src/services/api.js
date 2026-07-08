import { 
  mockHistory as initialMockHistory, 
  mockConvergedResponse, 
  mockNoViableAirfoilResponse, 
  mockValidationError422, 
  mockBadRequest400, 
  mockServerError500 
} from './mockData';

// API client for connecting to FastAPI backend or serving mock data
const API_BASE = '/api/v1';

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// Maintain a mutable history list in memory for mock mode
let mockHistoryData = [...initialMockHistory];

export const api = {
  async runDesign(rules, useLlm, maxIterations, mockMode = true, mockScenario = 'converged', onProgress = () => {}) {
    if (mockMode) {
      const simulateEvent = async (evt, ms) => {
        onProgress(evt);
        await delay(ms);
      };

      await simulateEvent({ type: "status", message: "Initializing optimizer in Mock Mode..." }, 150);
      await simulateEvent({ type: "node_start", node: "ingest_rules" }, 150);
      await simulateEvent({ type: "node_complete", node: "ingest_rules", variables: { iteration: 0 } }, 150);

      await simulateEvent({ type: "node_start", node: "seed_design" }, 150);
      await simulateEvent({ type: "node_complete", node: "seed_design", variables: { iteration: 0, wing_area_m2: 0.85, aspect_ratio: 8.2, span_m: 2.64 } }, 150);

      await simulateEvent({ type: "node_start", node: "evaluate_aero" }, 150);
      await simulateEvent({ type: "node_complete", node: "evaluate_aero", variables: { iteration: 0, CL_cruise: 0.52, CD_total: 0.031 } }, 150);

      await simulateEvent({ type: "node_start", node: "select_airfoil" }, 150);
      await simulateEvent({ type: "airfoil_progress", airfoil_id: "clarky", status: "passed", details: { score: 16.8, L_D: 16.8, CL_max: 1.39 } }, 100);
      await simulateEvent({ type: "airfoil_progress", airfoil_id: "n0012", status: "skipped_thickness", details: { thickness: 0.12 } }, 100);
      await simulateEvent({ type: "airfoil_progress", airfoil_id: "s1223", status: "passed", details: { score: 14.2, L_D: 14.2, CL_max: 1.45 } }, 100);
      await simulateEvent({ type: "node_complete", node: "select_airfoil", variables: { airfoil_id: "clarky" } }, 150);

      await simulateEvent({ type: "node_start", node: "check_constraints" }, 150);

      const id = `design-${Math.random().toString(36).substr(2, 6)}`;
      const timestamp = new Date().toISOString();

      let result;
      switch (mockScenario) {
        case 'converged':
          result = JSON.parse(JSON.stringify(mockConvergedResponse));
          result.design.MTOW_kg = Number(rules.MTOW_kg) || 5.0;
          break;
        case 'best_effort':
          result = JSON.parse(JSON.stringify(mockConvergedResponse));
          result.status = 'best_effort';
          result.converged = false;
          result.iterations_used = 10;
          result.violations = [
            {
              "parameter": "span_m",
              "limit": rules.max_wingspan_m ? Number(rules.max_wingspan_m) : 2.0,
              "actual": rules.max_wingspan_m ? Number(rules.max_wingspan_m) + 0.2 : 2.2,
              "severity": "soft",
              "suggestion": "slightly reduce aspect ratio or wing area"
            }
          ];
          result.design.MTOW_kg = Number(rules.MTOW_kg) || 5.0;
          break;
        case 'no_viable_airfoil':
          result = JSON.parse(JSON.stringify(mockNoViableAirfoilResponse));
          break;
        case 'validation_422':
          // If custom path is empty, make a custom message
          const err422 = JSON.parse(JSON.stringify(mockValidationError422));
          if (rules.custom_airfoil_paths && rules.custom_airfoil_paths.length > 0) {
            err422.detail[0].msg = `Custom airfoil .dat file failed validate_dat_file(): coordinates count must be between 20 and 300. The uploaded file '${rules.custom_airfoil_paths[0]}' contains only 12 coordinate points.`;
          }
          return { ok: false, status: 422, data: err422 };
        
        // NOTE: bad_request_400 is unreachable via the Live API.
        // This is because Pydantic handles backend request validation and returns a
        // 422 Unprocessable Entity for missing or malformed request parameters.
        // We keep it here as a pure UI-robustness test.
        case 'bad_request_400':
          return { ok: false, status: 400, data: mockBadRequest400 };
        case 'server_error_500':
        default:
          return { ok: false, status: 500, data: mockServerError500 };
      }

      // Add metadata to result
      result.id = id;
      result.created_at = timestamp;

      // Add to mutable mock history
      const newHistoryItem = {
        id: id,
        timestamp: timestamp,
        status: result.status,
        competition_rules: rules,
        design: result.design
      };
      mockHistoryData.unshift(newHistoryItem);

      await simulateEvent({ type: "node_complete", node: "finalize_design", variables: { converged: result.converged } }, 150);

      return { ok: true, status: 200, data: result };
    }

    try {
      const response = await fetch(`${API_BASE}/design/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          competition_rules: {
            MTOW_kg: rules.MTOW_kg ? Number(rules.MTOW_kg) : null,
            payload_kg: rules.payload_kg ? Number(rules.payload_kg) : null,
            max_wingspan_m: rules.max_wingspan_m ? Number(rules.max_wingspan_m) : null,
            KV_rating: rules.KV_rating ? Number(rules.KV_rating) : null,
            max_power_W: rules.max_power_W ? Number(rules.max_power_W) : null,
            min_stall_speed_ms: rules.min_stall_speed_ms ? Number(rules.min_stall_speed_ms) : null,
            target_cruise_speed_ms: rules.target_cruise_speed_ms ? Number(rules.target_cruise_speed_ms) : 15.0,
            custom_airfoil_paths: rules.custom_airfoil_paths || []
          },
          use_llm: useLlm,
          max_iterations: Number(maxIterations)
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        return {
          ok: false,
          status: response.status,
          data
        };
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      let finalResult = null;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        // Keep the last incomplete line in buffer
        buffer = lines.pop();

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith("data:")) {
            try {
              const eventData = JSON.parse(trimmed.slice(5).trim());
              if (eventData.type === "complete") {
                finalResult = eventData.result;
              }
              onProgress(eventData);
            } catch (e) {
              console.error("Failed to parse SSE line:", trimmed, e);
            }
          }
        }
      }

      if (finalResult) {
        return { ok: true, status: 200, data: finalResult };
      } else {
        return {
          ok: false,
          status: 500,
          data: { detail: "Stream completed without yielding the final optimization result." }
        };
      }
    } catch (err) {
      return {
        ok: false,
        status: 500,
        data: { detail: `Network stream connection failed: ${err.message}` }
      };
    }
  },

  async getHistory(mockMode = true) {
    if (mockMode) {
      await delay(400);
      return { ok: true, status: 200, data: [...mockHistoryData] };
    }

    try {
      const response = await fetch(`${API_BASE}/design/history?limit=20`);
      const data = await response.json();
      return { ok: response.ok, status: response.status, data };
    } catch (err) {
      return {
        ok: false,
        status: 500,
        data: { detail: `Failed to load design history: ${err.message}` }
      };
    }
  },

  async getDesignById(id, mockMode = true) {
    if (mockMode) {
      await delay(400);
      const match = mockHistoryData.find(item => item.id === id);
      if (match) {
        // Mock a full run details based on status
        let baseResponse = mockConvergedResponse;
        if (match.status === 'no_viable_airfoil') {
          baseResponse = mockNoViableAirfoilResponse;
        } else if (match.status === 'best_effort') {
          baseResponse = {
            ...mockConvergedResponse,
            status: 'best_effort',
            converged: false,
            iterations_used: 10,
            violations: [
              {
                "parameter": "span_m",
                "limit": match.competition_rules.max_wingspan_m ? Number(match.competition_rules.max_wingspan_m) : 2.0,
                "actual": match.competition_rules.max_wingspan_m ? Number(match.competition_rules.max_wingspan_m) + 0.2 : 2.2,
                "severity": "soft",
                "suggestion": "slightly reduce aspect ratio or wing area"
              }
            ]
          };
        }
        const details = JSON.parse(JSON.stringify(baseResponse));
        details.id = match.id;
        details.created_at = match.timestamp;
        details.status = match.status;
        if (match.design) {
          details.design = match.design;
        } else {
          details.design = null;
        }
        return { ok: true, status: 200, data: details };
      }
      return { ok: false, status: 404, data: { detail: "Design not found" } };
    }

    try {
      const response = await fetch(`${API_BASE}/design/${id}`);
      const data = await response.json();
      return { ok: response.ok, status: response.status, data };
    } catch (err) {
      return {
        ok: false,
        status: 500,
        data: { detail: `Failed to load design details: ${err.message}` }
      };
    }
  }
};
