// Research harness for the unmodified, MIT-licensed Emilie Gillet drum classes.
#include <cassert>
#include <cerrno>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include "plaits/dsp/drums/analog_bass_drum.h"
#include "plaits/dsp/drums/synthetic_bass_drum.h"

// Static zero initialization covers fields omitted by SyntheticBassDrum::Init().
static plaits::AnalogBassDrum analog;
static plaits::SyntheticBassDrum synthetic;

static float position(const char* text) {
  char* end;
  float value = std::strtof(text, &end);
  assert(*text && !*end && std::isfinite(value) && value >= 0 && value <= 1);
  return value;
}

int main(int argc, char** argv) {
  static_assert(sizeof(float) == 4, "capture requires float32");
  assert(argc == 7);
  bool is_analog = std::strcmp(argv[1], "analog") == 0;
  assert(is_analog || std::strcmp(argv[1], "synthetic") == 0);
  float tone = position(argv[2]), decay = position(argv[3]), fm = position(argv[4]);
  assert(std::strcmp(argv[5], "0") == 0 || std::strcmp(argv[5], "1") == 0);
  bool retrigger = argv[5][0] == '1';
  char* end;
  errno = 0;
  unsigned long seed = std::strtoul(argv[6], &end, 10);
  assert(*argv[6] && !*end && !errno && seed <= UINT32_MAX);
  stmlib::Random::Seed(static_cast<uint32_t>(seed));
  analog.Init();
  synthetic.Init();
  constexpr int block_size = 12, frames = 96000;
  float output[block_size];
  // One silent block primes the synthetic frequency interpolator before START.
  for (int n = -block_size; n < frames; n += block_size) {
    bool trigger = n == 0 || (retrigger && n == 7200);
    if (is_analog) {
      analog.Render(false, trigger, .8f, 55.f / 48000, tone, decay,
                    fm, fm, output, block_size);
    } else {
      synthetic.Render(false, trigger, .8f, 50.f / 48000, tone, decay,
                       .4f - .25f * decay * decay, fm, 0.f, output, block_size);
    }
    for (float sample : output) {
      assert(std::isfinite(sample));
      if (n < 0) assert(sample == 0.f);
    }
    if (n >= 0) assert(std::fwrite(output, sizeof(float), block_size, stdout) == block_size);
  }
  return std::fflush(stdout) == 0 ? 0 : 1;
}
