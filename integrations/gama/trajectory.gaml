/** Engineering fixture only: no biologically calibrated behaviour. */
model marlin_trajectory

global {
    float step <- 1.0;
    float phase <- rnd(360.0);
    float angle <- 0.0;
    float x_m <- 0.0;
    float z_m <- 0.0;
    float heading_deg <- 0.0;
    float time_s <- 0.0;
    float y_m <- -0.8;
    float speed_mps <- 12.0 * 3.0 * #pi / 180.0;
    reflex trajectory {
        time_s <- float(cycle);
        angle <- phase + 3.0 * time_s;
        x_m <- 12.0 * sin(angle);
        z_m <- 12.0 * cos(angle);
        heading_deg <- angle + 90.0 - 360.0 * floor((angle + 90.0) / 360.0);
    }
}

experiment fixture type: gui {
    output {
        monitor "time_s" value: time_s;
        monitor "x_m" value: x_m;
        monitor "z_m" value: z_m;
        monitor "heading_deg" value: heading_deg;
        monitor "y_m" value: y_m;
        monitor "speed_mps" value: speed_mps;
    }
}
