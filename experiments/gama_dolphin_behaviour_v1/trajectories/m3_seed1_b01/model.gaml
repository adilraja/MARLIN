/** Adapted from porpoise_behaviour.gaml's explicit-clock record-first pattern.
 * Engineering controls only. No biological calibration, renderer or body animation.
 */
model marlin_bottlenose_constrained_v1

global {
    float step <- 0.25;
    int requested_seed <- 184729;
    string exchange_run_id <- "bottlenose_reference";
    bool enable_variation <- false;
    float start_x_m <- -10.0;
    float start_z_m <- -15.0;
    float initial_heading_deg <- 350.0;
    float steady_s <- 10.0;
    float turn_s <- 12.0;
    float descent_s <- 16.0;
    float submerged_s <- 10.0;
    float ascent_s <- 16.0;
    float final_steady_s <- 10.0;
    float initial_depth_m <- 0.2;
    float target_depth_m <- 3.2;
    float cruise_speed_mps <- 0.8;
    float turn_angle_deg <- 75.0;
    float speed_ramp_s <- 4.0;
    float stationary_hold_s <- 2.0;
    float turn_spread_deg <- 10.0;
    float depth_spread_m <- 0.4;
    float speed_spread_mps <- 0.1;
    float animation_rate_hz <- 0.8;
    float initial_phase_cycles <- 0.25;
    float actual_seed <- 0.0;
    int random_draw_count <- 0;
    float realised_turn_deg <- 0.0;
    float realised_depth_m <- 0.0;
    float realised_speed_mps <- 0.0;
    int step_index <- 0;
    float simulation_time_s <- 0.0;
    float x_m <- 0.0;
    float z_m <- 0.0;
    float heading_deg <- 0.0;
    float pitch_deg <- 0.0;
    float roll_deg <- 0.0;
    float speed_mps <- 0.0;
    float vertical_velocity_mps <- 0.0;
    float vx_mps <- 0.0;
    float vz_mps <- 0.0;
    float depth_m <- 0.2;
    string behavioural_state <- "steady_swim";
    string episode <- "initial_steady";
    float state_entry_time_s <- 0.0;
    float transition_duration_s <- 10.0;
    float phase_epoch_time_s <- 0.0;
    float phase_epoch_cycles <- 0.25;
    float phase_rate_hz <- 0.0;

    init {
        seed <- float(requested_seed);
        actual_seed <- seed;
        realised_turn_deg <- turn_angle_deg;
        realised_depth_m <- target_depth_m;
        realised_speed_mps <- cruise_speed_mps;
        if enable_variation {
            realised_turn_deg <- turn_angle_deg + rnd(2.0 * turn_spread_deg) - turn_spread_deg;
            realised_depth_m <- target_depth_m + rnd(2.0 * depth_spread_m) - depth_spread_m;
            realised_speed_mps <- cruise_speed_mps + rnd(2.0 * speed_spread_mps) - speed_spread_mps;
            random_draw_count <- 3;
        }
        x_m <- start_x_m;
        z_m <- start_z_m;
        phase_epoch_cycles <- initial_phase_cycles;
        create bottlenose number: 1;
    }

    reflex update_clock {
        step_index <- cycle;
        simulation_time_s <- float(cycle) * step;
    }
}

species bottlenose {
    reflex controlled_sample {
        float t <- simulation_time_s;
        float turn_end <- steady_s + turn_s;
        float descent_end <- turn_end + descent_s;
        float submerged_end <- descent_end + submerged_s;
        float ascent_end <- submerged_end + ascent_s;
        float end_s <- ascent_end + final_steady_s;
        float previous_vx <- vx_mps;
        float previous_vz <- vz_mps;
        float previous_rate <- phase_rate_hz;
        float phase_now <- phase_epoch_cycles;
        if step_index > 0 { phase_now <- phase_now + previous_rate * step; }
        phase_epoch_cycles <- phase_now - floor(phase_now);
        phase_epoch_time_s <- t;

        // Equivalent timed state machine: thresholds are elapsed SI seconds.
        float u <- 0.0;
        float depth_change <- 0.0;
        depth_m <- initial_depth_m;
        vertical_velocity_mps <- 0.0;
        heading_deg <- initial_heading_deg;
        if t < steady_s {
            behavioural_state <- "steady_swim"; episode <- "initial_steady";
            state_entry_time_s <- 0.0; transition_duration_s <- steady_s;
        } else if t < turn_end {
            behavioural_state <- "turn"; episode <- "turn";
            state_entry_time_s <- steady_s; transition_duration_s <- turn_s;
            u <- (t - steady_s) / turn_s;
            heading_deg <- initial_heading_deg + realised_turn_deg * u*u*u*(10.0 + u*(-15.0 + 6.0*u));
        } else if t < descent_end {
            behavioural_state <- "descent"; episode <- "descent";
            state_entry_time_s <- turn_end; transition_duration_s <- descent_s;
            u <- (t - turn_end) / descent_s;
            depth_change <- realised_depth_m - initial_depth_m;
            depth_m <- initial_depth_m + depth_change * u*u*u*(10.0 + u*(-15.0 + 6.0*u));
            vertical_velocity_mps <- -depth_change * 30.0*u*u*(1.0-u)*(1.0-u) / descent_s;
        } else if t < submerged_end {
            behavioural_state <- "submerged_swim"; episode <- "submerged_swim";
            state_entry_time_s <- descent_end; transition_duration_s <- submerged_s;
            depth_m <- realised_depth_m;
        } else if t < ascent_end {
            behavioural_state <- "ascent"; episode <- "ascent";
            state_entry_time_s <- submerged_end; transition_duration_s <- ascent_s;
            u <- (t - submerged_end) / ascent_s;
            depth_change <- initial_depth_m - realised_depth_m;
            depth_m <- realised_depth_m + depth_change * u*u*u*(10.0 + u*(-15.0 + 6.0*u));
            vertical_velocity_mps <- -depth_change * 30.0*u*u*(1.0-u)*(1.0-u) / ascent_s;
        } else {
            behavioural_state <- "steady_swim"; episode <- "final_steady";
            state_entry_time_s <- ascent_end; transition_duration_s <- final_steady_s;
        }
        if t >= turn_end { heading_deg <- initial_heading_deg + realised_turn_deg; }
        heading_deg <- heading_deg - 360.0 * floor(heading_deg / 360.0);

        // Smooth start/stop; all manoeuvre boundaries have the same cruise speed.
        speed_mps <- realised_speed_mps;
        if t <= stationary_hold_s { speed_mps <- 0.0; }
        else if t < stationary_hold_s + speed_ramp_s {
            float v <- (t - stationary_hold_s) / speed_ramp_s;
            speed_mps <- realised_speed_mps * v*v*v*(10.0 + v*(-15.0 + 6.0*v));
        } else if t >= end_s - stationary_hold_s { speed_mps <- 0.0; }
        else if t > end_s - stationary_hold_s - speed_ramp_s {
            float v <- (t - end_s + stationary_hold_s + speed_ramp_s) / speed_ramp_s;
            speed_mps <- realised_speed_mps * (1.0 - v*v*v*(10.0 + v*(-15.0 + 6.0*v)));
        }
        pitch_deg <- 0.0;
        if speed_mps > 0.0 { pitch_deg <- atan(vertical_velocity_mps / speed_mps); }
        roll_deg <- 0.0;
        vx_mps <- speed_mps * sin(heading_deg);
        vz_mps <- speed_mps * cos(heading_deg);
        if step_index > 0 {
            x_m <- x_m + step * (previous_vx + vx_mps) / 2.0;
            z_m <- z_m + step * (previous_vz + vz_mps) / 2.0;
        }
        phase_rate_hz <- 0.0;
        if speed_mps > 0.0 { phase_rate_hz <- animation_rate_hz; }
    }
}

experiment record_bottlenose_v3 type: gui {
    parameter "step" var: step;
    parameter "requested_seed" var: requested_seed;
    parameter "exchange_run_id" var: exchange_run_id;
    parameter "enable_variation" var: enable_variation;
    parameter "start_x_m" var: start_x_m;
    parameter "start_z_m" var: start_z_m;
    parameter "initial_heading_deg" var: initial_heading_deg;
    parameter "steady_s" var: steady_s;
    parameter "turn_s" var: turn_s;
    parameter "descent_s" var: descent_s;
    parameter "submerged_s" var: submerged_s;
    parameter "ascent_s" var: ascent_s;
    parameter "final_steady_s" var: final_steady_s;
    parameter "initial_depth_m" var: initial_depth_m;
    parameter "target_depth_m" var: target_depth_m;
    parameter "cruise_speed_mps" var: cruise_speed_mps;
    parameter "turn_angle_deg" var: turn_angle_deg;
    parameter "speed_ramp_s" var: speed_ramp_s;
    parameter "stationary_hold_s" var: stationary_hold_s;
    parameter "turn_spread_deg" var: turn_spread_deg;
    parameter "depth_spread_m" var: depth_spread_m;
    parameter "speed_spread_mps" var: speed_spread_mps;
    parameter "animation_rate_hz" var: animation_rate_hz;
    parameter "initial_phase_cycles" var: initial_phase_cycles;
    output {
        monitor "enable_variation" value: enable_variation;
        monitor "phase_version" value: "constant_rate_v1";
        monitor "cfg_step" value: step;
        monitor "cfg_start_x_m" value: start_x_m;
        monitor "cfg_start_z_m" value: start_z_m;
        monitor "cfg_initial_heading_deg" value: initial_heading_deg;
        monitor "cfg_steady_s" value: steady_s;
        monitor "cfg_turn_s" value: turn_s;
        monitor "cfg_descent_s" value: descent_s;
        monitor "cfg_submerged_s" value: submerged_s;
        monitor "cfg_ascent_s" value: ascent_s;
        monitor "cfg_final_steady_s" value: final_steady_s;
        monitor "cfg_initial_depth_m" value: initial_depth_m;
        monitor "cfg_target_depth_m" value: target_depth_m;
        monitor "cfg_cruise_speed_mps" value: cruise_speed_mps;
        monitor "cfg_turn_angle_deg" value: turn_angle_deg;
        monitor "cfg_speed_ramp_s" value: speed_ramp_s;
        monitor "cfg_stationary_hold_s" value: stationary_hold_s;
        monitor "cfg_turn_spread_deg" value: turn_spread_deg;
        monitor "cfg_depth_spread_m" value: depth_spread_m;
        monitor "cfg_speed_spread_mps" value: speed_spread_mps;
        monitor "cfg_animation_rate_hz" value: animation_rate_hz;
        monitor "cfg_initial_phase_cycles" value: initial_phase_cycles;
        monitor "schema_version" value: "3.0";
        monitor "model_version" value: "bottlenose_constrained_v1";
        monitor "run_id" value: exchange_run_id;
        monitor "agent_id" value: "Bottlenose_001";
        monitor "species" value: "bottlenose_dolphin";
        monitor "vertical_reference" value: "mean_sea_level";
        monitor "agent_count" value: length(bottlenose);
        monitor "actual_seed" value: actual_seed;
        monitor "random_draw_count" value: random_draw_count;
        monitor "realised_turn_deg" value: realised_turn_deg;
        monitor "realised_depth_m" value: realised_depth_m;
        monitor "realised_speed_mps" value: realised_speed_mps;
        monitor "step_index" value: step_index;
        monitor "simulation_time_s" value: simulation_time_s;
        monitor "simulation_step_s" value: step;
        monitor "behavioural_state" value: behavioural_state;
        monitor "episode" value: episode;
        monitor "x_m" value: x_m;
        monitor "z_m" value: z_m;
        monitor "heading_deg" value: heading_deg;
        monitor "pitch_deg" value: pitch_deg;
        monitor "roll_deg" value: roll_deg;
        monitor "speed_mps" value: speed_mps;
        monitor "vertical_velocity_mps" value: vertical_velocity_mps;
        monitor "vx_mps" value: vx_mps;
        monitor "vz_mps" value: vz_mps;
        monitor "depth_m" value: depth_m;
        monitor "state_entry_time_s" value: state_entry_time_s;
        monitor "transition_duration_s" value: transition_duration_s;
        monitor "phase_epoch_time_s" value: phase_epoch_time_s;
        monitor "phase_epoch_cycles" value: phase_epoch_cycles;
        monitor "phase_rate_hz" value: phase_rate_hz;
    }
}
