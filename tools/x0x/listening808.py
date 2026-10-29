"""Native audio listening material for the current 808 model."""
import base64
import io
import json
from pathlib import Path
from . import fit808

CORNERS=[(0,0),(0,127),(127,0),(127,127)]

def listening_report(output, events, references, predictions, manifest):
    import numpy as np
    import soundfile as sf
    peak = max(float(np.max(abs(y))) for y in [*references.values(), *predictions.values()])
    gain = min(4., .95 / peak)
    stimuli = []
    for event in events:
        pair = event['tone_cc'], event['decay_cc']
        data = dict(tone=pair[0], decay=pair[1])
        for name, samples in (('recorded', references[pair]), ('candidate', predictions[pair])):
            stream = io.BytesIO()
            # Native media playback needs no Web Audio gain node or float-WAV decoder.
            sf.write(stream, samples * gain, fit808.RATE, format='WAV', subtype='PCM_24')
            data[name] = base64.b64encode(stream.getvalue()).decode('ascii')
            filename = f't{pair[0]:03}-d{pair[1]:03}-{name}-playback.wav'
            (output / filename).write_bytes(stream.getvalue())
            data[name + '_download'] = filename
        stimuli.append(data)
    template_path = Path(__file__).with_suffix('.html')
    manifest = dict(manifest, listening_template_sha256=fit808.digest(template_path),
                    response_policy='a-b-or-cant-tell-v1')
    payload = json.dumps(dict(stimuli=stimuli, gain=gain, gain_applied=True,
                             playback_encoding='PCM_24', manifest=manifest), allow_nan=False).replace('<', '\\u003c')
    template = Path(__file__).with_suffix('.html').read_text()
    (output / 'index.html').write_text(template.replace('__LISTENING_DATA__', payload))
    return gain

