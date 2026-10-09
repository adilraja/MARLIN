/** engineering_porpoise_v1: timed demonstration, NOT calibrated biology.
 * One external actor, explicit SI outputs; no MARLIN/rendering side effects.
 */
model marlin_porpoise_behaviour

global {
    float step <- 0.5;
    int requested_seed <- 184729;
    string exchange_run_id <- "porpoise_demo";
    float actual_seed <- 0.0;
    float initial_phase_deg <- 0.0;
    float path_radius_m <- 8.0;
    float horizontal_speed_mps <- 0.5;
    float surface_depth_m <- 0.2;
    float shallow_depth_m <- 0.8;
    float submerged_depth_m <- 3.0;
    float initial_surface_s <- 2.0;
    float shallow_swim_s <- 4.0;
    float descent_s <- 4.0;
    float submerged_swim_s <- 4.0;
    float ascent_s <- 4.0;
    float final_surface_s <- 2.0;
    int step_index <- 0;
    float simulation_time_s <- 0.0;
    float x_m <- 0.0;
    float z_m <- 0.0;
    float heading_deg <- 0.0;
    float depth_m <- 0.2;
    string behavioural_state <- "surface";

    init {
        // Reset explicitly before the only random draw. Export the actual RNG seed.
        seed <- float(requested_seed);
        actual_seed <- seed;
        initial_phase_deg <- rnd(360.0);
        create porpoise number: 1;
    }

    reflex update_clock {
        step_index <- cycle;
        simulation_time_s <- float(cycle) * step;
    }
}

species porpoise control: fsm {
    action horizontal_sample {
        float angle <- initial_phase_deg + horizontal_speed_mps * simulation_time_s / path_radius_m * 180.0 / #pi;
        x_m <- path_radius_m * sin(angle);
        z_m <- path_radius_m * cos(angle);
        heading_deg <- angle + 90.0 - 360.0 * floor((angle + 90.0) / 360.0);
    }

    state surface initial: true {
        behavioural_state <- "surface";
        depth_m <- surface_depth_m;
        do horizontal_sample;
        // Decide the next sample's state; the exported label is the body executed.
        transition to: shallow_swim when: simulation_time_s + step >= initial_surface_s;
    }

    state shallow_swim {
        behavioural_state <- "shallow_swim";
        float u <- (simulation_time_s - initial_surface_s) / shallow_swim_s;
        depth_m <- surface_depth_m + (shallow_depth_m - surface_depth_m) * u * u * (3.0 - 2.0 * u);
        do horizontal_sample;
        transition to: descent when: simulation_time_s + step >= initial_surface_s + shallow_swim_s;
    }

    state descent {
        behavioural_state <- "descent";
        float u <- (simulation_time_s - initial_surface_s - shallow_swim_s) / descent_s;
        depth_m <- shallow_depth_m + (submerged_depth_m - shallow_depth_m) * u * u * (3.0 - 2.0 * u);
        do horizontal_sample;
        transition to: submerged_swim when: simulation_time_s + step >= initial_surface_s + shallow_swim_s + descent_s;
    }

    state submerged_swim {
        behavioural_state <- "submerged_swim";
        depth_m <- submerged_depth_m;
        do horizontal_sample;
        transition to: ascent when: simulation_time_s + step >= initial_surface_s + shallow_swim_s + descent_s + submerged_swim_s;
    }

    state ascent {
        behavioural_state <- "ascent";
        float u <- (simulation_time_s - initial_surface_s - shallow_swim_s - descent_s - submerged_swim_s) / ascent_s;
        depth_m <- submerged_depth_m + (surface_depth_m - submerged_depth_m) * u * u * (3.0 - 2.0 * u);
        do horizontal_sample;
        transition to: final_surface when: simulation_time_s + step >= initial_surface_s + shallow_swim_s + descent_s + submerged_swim_s + ascent_s;
    }

    state final_surface {
        behavioural_state <- "surface";
        depth_m <- surface_depth_m;
        do horizontal_sample;
    }
}

// Legacy headless uses a gui-type experiment without requiring a GUI/display.
experiment record_porpoise type: gui {
    parameter "step" var: step;
    parameter "requested_seed" var: requested_seed;
    parameter "exchange_run_id" var: exchange_run_id;
    parameter "path_radius_m" var: path_radius_m;
    parameter "horizontal_speed_mps" var: horizontal_speed_mps;
    parameter "surface_depth_m" var: surface_depth_m;
    parameter "shallow_depth_m" var: shallow_depth_m;
    parameter "submerged_depth_m" var: submerged_depth_m;
    parameter "initial_surface_s" var: initial_surface_s;
    parameter "shallow_swim_s" var: shallow_swim_s;
    parameter "descent_s" var: descent_s;
    parameter "submerged_swim_s" var: submerged_swim_s;
    parameter "ascent_s" var: ascent_s;
    parameter "final_surface_s" var: final_surface_s;
    output {
        monitor "schema_version" value: "2.0";
        monitor "run_id" value: exchange_run_id;
        monitor "agent_id" value: "Porpoise_001";
        monitor "species" value: "harbour_porpoise";
        monitor "vertical_reference" value: "mean_sea_level";
        monitor "agent_count" value: length(porpoise);
        monitor "step_index" value: step_index;
        monitor "simulation_time_s" value: simulation_time_s;
        monitor "simulation_step_s" value: step;
        monitor "actual_seed" value: actual_seed;
        monitor "initial_phase_deg" value: initial_phase_deg;
        monitor "behavioural_state" value: behavioural_state;
        monitor "x_m" value: x_m;
        monitor "z_m" value: z_m;
        monitor "heading_deg" value: heading_deg;
        monitor "speed_mps" value: horizontal_speed_mps;
        monitor "depth_m" value: depth_m;
        monitor "path_radius_m" value: path_radius_m;
        monitor "surface_depth_m" value: surface_depth_m;
        monitor "shallow_depth_m" value: shallow_depth_m;
        monitor "submerged_depth_m" value: submerged_depth_m;
        monitor "initial_surface_s" value: initial_surface_s;
        monitor "shallow_swim_s" value: shallow_swim_s;
        monitor "descent_s" value: descent_s;
        monitor "submerged_swim_s" value: submerged_swim_s;
        monitor "ascent_s" value: ascent_s;
        monitor "final_surface_s" value: final_surface_s;
    }
}
