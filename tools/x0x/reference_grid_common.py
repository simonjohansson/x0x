"""Small shared bootstrap for the two actual-CPU training-grid diagnostics."""
import hashlib
import inspect
import io
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import textwrap

ROOT = Path(__file__).resolve().parents[2]
ACCEPTED = '65aeaf7a76a55248903f2eec2b464752711defd7'


def _git(*arguments, cwd=ROOT):
    return subprocess.check_output(['git', *arguments], cwd=cwd)


def prepare_frozen(path, revision=ACCEPTED):
    """Archive tracked code and use only vendor checkouts at its exact gitlinks."""
    path = Path(path).resolve()
    commit = _git('rev-parse', revision).decode().strip()
    if not path.exists():
        path.mkdir(parents=True)
        with tarfile.open(fileobj=io.BytesIO(_git('archive', '--format=tar', commit))) as archive:
            archive.extractall(path, filter='data')
    names = _git('ls-tree', '-r', '--name-only', commit, '--', 'tools/x0x', 'targets', 'machines').decode().splitlines()
    hashes = {}
    for name in names:
        expected = _git('show', f'{commit}:{name}')
        if not (path/name).is_file() or (path/name).read_bytes() != expected:
            raise ValueError(f'frozen source differs from {commit}: {name}')
        hashes[name] = hashlib.sha256(expected).hexdigest()
    pins = {}
    for name in ('digiemu', 'digikit', 'elekloader'):
        line = _git('ls-tree', commit, f'vendor/{name}').decode().split()
        assert line[0] == '160000'
        pin = line[2]; vendor = ROOT/'vendor'/name
        if _git('rev-parse', 'HEAD', cwd=vendor).decode().strip() != pin:
            raise ValueError(f'vendor/{name} must be at accepted gitlink {pin}')
        if _git('diff', '--name-only', 'HEAD', cwd=vendor).strip():
            raise ValueError(f'vendor/{name} has tracked edits outside the accepted gitlink')
        destination = path/'vendor'/name
        if destination.exists() and not destination.is_symlink():
            destination.rmdir()  # Git archive leaves, at most, an empty gitlink directory.
        if not destination.is_symlink():
            destination.symlink_to(vendor, target_is_directory=True)
        if destination.resolve() != vendor.resolve():
            raise ValueError(f'wrong frozen vendor link: {destination}')
        pins[name] = pin
    return dict(commit=commit, frozen_source_root=str(path), pins=pins, source_sha256=hashes)


def frozen_invocation(script, arguments, frozen_path):
    """Re-enter a tracked direct-file driver with frozen x0x modules first."""
    frozen_path = Path(frozen_path).resolve()
    environment = dict(os.environ)
    environment['PYTHONPATH'] = os.pathsep.join(str(p) for p in
        [frozen_path/'tools', ROOT/'vendor/digiemu', ROOT/'vendor/digikit', ROOT/'vendor/elekloader'])
    return subprocess.call([sys.executable, str(Path(script).resolve()), *arguments],
                           cwd=ROOT, env=environment)


def runner_class(original, *, state_words=None):
    """Optional diagnostic batching; actual render/post-call guards stay intact.

    Only the two global Python logging hooks are omitted. This does not claim
    per-instruction write ownership watching for the long batch.
    """
    from x0x import coldfire_body808 as accepted
    source = textwrap.dedent(inspect.getsource(accepted.Runner.__init__))
    filtered = source
    for hook in ('self.uc.hook_add(UC_HOOK_CODE, self._step)',
                 'self.uc.hook_add(UC_HOOK_MEM_WRITE, self._write)'):
        assert filtered.count(hook) == 1
        filtered = filtered.replace(hook, 'pass  # batch logging omitted; post-call guards retained')
    namespace = dict(vars(accepted))
    exec(compile(filtered, __file__ + ':accepted-constructor', 'exec'), namespace)
    constructor = namespace['__init__']
    if state_words is not None:
        def with_words(self, image):
            constructor(self, image, state_words=state_words)
        initializer = with_words
    else:
        initializer = constructor
    return type('Batch' + original.__name__, (original,), {'__init__': initializer})
