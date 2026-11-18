// host_replay.cpp
// The same replay as refit_replay_board.ino, on a computer. Needs g++ and replay_data.h in this folder:
//     g++ -O2 -o host_replay host_replay.cpp && ./host_replay
#include <cstdio>
#include "replay_data.h"
#include "replay_runner.h"

template <int CAL, int WIN, int PERSIST>
void runAll() {
  for (int s = 0; s < N_SERIES; s++) {
    ReplayResult r = replaySeries<CAL, WIN, PERSIST>(SERIES[s].data, SERIES[s].n);
    printf("RESULT|%s|CAL=%d WIN=%d P=%d|evals=%lu|lvl0=%lu|lvl1=%lu|lvl2=%lu|hash=%08lX\n",
           SERIES[s].name, CAL, WIN, PERSIST, (unsigned long)r.evals, (unsigned long)r.lvl0,
           (unsigned long)r.lvl1, (unsigned long)r.lvl2, (unsigned long)r.hash);
  }
}

int main() {
  runAll<3, 5, 1>();
  runAll<24, 5, 6>();
  return 0;
}
