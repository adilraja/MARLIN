/** Live engineering fixture; keep the already-verified file fixture unchanged. */
model marlin_trajectory_live
import "trajectory.gaml"

global {
    init {
        // Reset RNG before the phase draw, independently of GUI/server preferences.
        seed <- 184729.0;
        phase <- rnd(360.0);
    }
}

experiment live_fixture type: gui { }
