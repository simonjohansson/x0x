/* Private feasibility benchmark, not a native callback or production DSP port.
 * The generated header contains the frozen model, not newly fitted parameters. */
#include "field808_tables.h"

struct field_state {
    float coefficient[299];
    unsigned sample, phase_hi, phase_lo;
    float tone_state, pole, gain;
    float polynomial[28], left[4], right[4], inverse[4];
    unsigned valid;
};
const unsigned sharc_voice_state_bytes = sizeof(struct field_state);
struct field_input {
    struct field_state *state;
    float *output;
    unsigned start, decay;
    float pole;
};

/* Local cubic basis; the paired sine/cosine envelopes share its four weights. */
static int basis(float t, const float *knots, int count, float *b)
{
    float l1, l2, l3, r1, r2, r3, a, c, saved;
    int span = 3;
    if (t < knots[3]) t = knots[3];
    if (t > knots[count]) t = knots[count];
    while (span < count - 1 && t >= knots[span + 1]) ++span;
    l1 = t - knots[span]; r1 = knots[span + 1] - t;
    l2 = t - knots[span - 1]; r2 = knots[span + 2] - t;
    l3 = t - knots[span - 2]; r3 = knots[span + 3] - t;
    a = 1.0f / (r1 + l1); b[0] = r1 * a; b[1] = l1 * a;
    a = b[0] / (r1 + l2); c = b[1] / (r2 + l1);
    b[0] = r1 * a; b[1] = l2 * a + r2 * c; b[2] = l1 * c;
    a = b[0] / (r1 + l3); saved = l3 * a; b[0] = r1 * a;
    a = b[1] / (r2 + l2); c = l2 * a; b[1] = saved + r2 * a;
    a = b[2] / (r3 + l1); b[2] = c + r3 * a; b[3] = l1 * a;
    return span - 3;
}

static void prepare(struct field_state *s, unsigned raw, float pole)
{
    float b[4], w[8], mix[4], sum, coordinate, fraction;
    unsigned cc = raw >> 8, lo, hi;
    int at, i, j, k, rank, width, offset;
    lo = (cc * 255 + 63) / 127;
    hi = cc == 127 ? lo : ((cc + 1) * 255 + 63) / 127;
    fraction = (float)(raw & 255) * (1.0f / 256.0f);
    coordinate = ((float)lo + fraction * (float)(hi - lo)) * (1.0f / 255.0f);
    at = basis(coordinate, control_knots, 19, b);
    for (i = 0; i < 8; ++i) {
        sum = 0.0f;
        for (j = 0; j < 4; ++j) sum += b[j] * (float)control[i * 19 + at + j];
        w[i] = sum * control_scale[i];
    }
    offset = 0;
    for (k = 0; k < 4; ++k) {
        rank = ranks[k]; width = widths[k];
        if (k < 2) {
            for (i = 0; i < rank; ++i) {
                sum = 0.0f;
                for (j = 0; j < 8; ++j) sum += w[j] * (float)mix_tables[k][i * 8 + j];
                mix[i] = sum * mix_scales[k][i];
            }
        }
        for (j = 0; j < width; ++j) {
            sum = 0.0f;
            for (i = 0; i < rank; ++i)
                sum += (k < 2 ? mix[i] : w[i]) * ((float)body_tables[k][i * width + j] * body_scales[k][i]);
            s->coefficient[offset + j] = sum;
        }
        offset += width;
    }
    s->sample = s->phase_hi = s->phase_lo = 0;
    s->valid = 0;
    s->tone_state = 0.0f;
    s->pole = pole;
    s->gain = (1.0f - pole) / (1.0f - CANONICAL_POLE);
}

static float sine(unsigned phase)
{
    float x = (float)(int)phase * (1.0f / 4294967296.0f), z;
    if (x > .25f) x = .5f - x;
    if (x < 0.0f - .25f) x = (0.0f - .5f) - x;
    x *= 6.283185307179586f;
    z = x * x;
    return x * (1.0f - z * (1.0f / 6.0f - z * (1.0f / 120.0f - z *
           (1.0f / 5040.0f - z * (1.0f / 362880.0f - z / 39916800.0f)))));
}

static void envelope(struct field_state *s, int h, int offset, float time, float *values)
{
    float b[4], samples[4], u, a, c, d, width;
    int base, span, i, j, k, channels = h == 3 ? 1 : 2;
    const float *knots = envelope_tables[h];
    int count = envelope_counts[h];
    int channel = 2 * h;
    if (!(s->valid & (1u << h)) || time >= s->right[h] || time < s->left[h]) {
        base = basis(time, knots, count, b); span = base + 3;
        s->left[h] = knots[span]; s->right[h] = knots[span + 1];
        width = s->right[h] - s->left[h]; s->inverse[h] = 1.0f / width;
        for (i = 0; i < channels; ++i) {
            for (j = 0; j < 4; ++j) {
                u = s->left[h] + width * (float)j * (1.0f / 3.0f);
                base = basis(u, knots, count, b); a = 0.0f;
                for (k = 0; k < 4; ++k) a += b[k] * s->coefficient[offset + i * count + base + k];
                samples[j] = a;
            }
            d = 4.5f * (samples[3] - 3.0f * samples[2] + 3.0f * samples[1] - samples[0]);
            c = 4.5f * (samples[2] - 2.0f * samples[1] + samples[0]) - d;
            a = 3.0f * (samples[1] - samples[0]) - c * (1.0f / 3.0f) - d * (1.0f / 9.0f);
            s->polynomial[4 * (channel + i)] = d;
            s->polynomial[4 * (channel + i) + 1] = c;
            s->polynomial[4 * (channel + i) + 2] = a;
            s->polynomial[4 * (channel + i) + 3] = samples[0];
        }
        s->valid |= 1u << h;
    }
    u = (time - s->left[h]) * s->inverse[h];
    for (i = 0; i < channels; ++i) {
        const float *p = s->polynomial + 4 * (channel + i);
        values[i] = ((p[0] * u + p[1]) * u + p[2]) * u + p[3];
    }
}

void sharc_voice_render(const struct field_input *in)
{
    struct field_state *s = in->state;
    float b[4], sn, cs, next, sn2, cs2, sn3, cs3, wave[7];
    float time, fade, onset, body, x, out, values[2];
    unsigned previous;
    int n, i, j, h, at, offset, channel;
    if (in->start) prepare(s, in->decay, in->pole);
    sn = sine(s->phase_hi);
    cs = sine(s->phase_hi + 0x40000000u);
    for (n = 0; n < 32; ++n) {
        if (s->sample >= 264000) { in->output[n] = 0.0f; continue; }
        time = (float)s->sample * (1.0f / 48000.0f);
        fade = (time - .020f) * 100.0f;
        if (fade < 0.0f) fade = 0.0f;
        if (fade > 1.0f) fade = 1.0f;
        fade = fade * fade * (3.0f - 2.0f * fade);
        onset = body = 0.0f;
        if (s->sample < 1440) {
            at = basis(time, raw_knots, 201, b);
            for (j = 0; j < 4; ++j)
                if (at + j) onset += b[j] * s->coefficient[at + j - 1];
        }
        if (s->sample >= 960) {
            sn2 = 2.0f * sn * cs; cs2 = cs * cs - sn * sn;
            sn3 = sn2 * cs + cs2 * sn; cs3 = cs2 * cs - sn2 * sn;
            wave[0] = sn; wave[1] = cs; wave[2] = sn2; wave[3] = cs2;
            wave[4] = sn3; wave[5] = cs3; wave[6] = 1.0f;
            offset = 200; channel = 0;
            for (h = 0; h < 4; ++h) {
                envelope(s, h, offset, time, values);
                for (i = 0; i < (h == 3 ? 1 : 2); ++i) {
                    body += values[i] * wave[channel++];
                }
                offset += (h == 3 ? 1 : 2) * envelope_counts[h];
            }
        }
        x = (1.0f - fade) * onset + fade * body;
        out = s->gain * x + s->tone_state;
        s->tone_state = s->pole * out - s->gain * CANONICAL_POLE * x;
        in->output[n] = out;
        next = sn * STEP_COS + cs * STEP_SIN;
        cs = cs * STEP_COS - sn * STEP_SIN;
        sn = next;
        ++s->sample;
    }
    previous = s->phase_lo;
    s->phase_lo += PHASE_STEP_LO;
    s->phase_hi += PHASE_STEP_HI + (s->phase_lo < previous);
}

unsigned field_state_size(void) { return sizeof(struct field_state); }
