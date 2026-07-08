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
  async runDesign(rules, useLlm, maxIterations, mockMode = true, mockScenario = 'converged') {
    if (mockMode) {
      await delay(800); // Simulate network latency

      const id = `design-${Math.random().toString(36).substr(2, 6)}`;
      const timestamp = new Date().toISOString();

      let result;
      switch (mockScenario) {
        case 'converged':
          // Merge actual rules for display in results
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

      return { ok: true, status: 200, data: result };
    }

    try {
      const response = await fetch(`${API_BASE}/design`, {
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

      const data = await response.json();
      return {
        ok: response.ok,
        status: response.status,
        data
      };
    } catch (err) {
      return {
        ok: false,
        status: 500,
        data: { detail: `Network connection failed: ${err.message}` }
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
