"""Read-only, source-pinned carried-start admission from the raw public CLI log.

This establishes initial start admission only. The caller must retain solver.log
and separately apply the unchanged process, identity, warning and final-status
gates. No line is removed or rewritten here; in particular, this is not a claim
that ordinary later incumbent postsolve never uses a repair LP.
"""
from current_scuc._paths import ROOT as PACKAGE_ROOT, source_path, source_sha, module as load_module, runtime_path, runtime_sha
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import hashlib
import math
from pathlib import Path
import re
import sys


SOURCE_COMMIT = 'd547a3ad8af5399651187fb0e133cf0e42615b82'
SOURCE_ROOT = None
SOURCE_PINS = {
    'highs/mip/HighsMipSolverData.cpp': 'eaafcf91b4653c17807b171720f66828dd6b18737dbf8b9b213cc58c8e022f33',
    'highs/mip/HighsMipSolver.cpp': '470b29456b3e481c38888cf0ccb1285a140586cbd60cf4da7fa62df439255598',
    'highs/lp_data/Highs.cpp': '6f84c2f12277e7bf335b13e0ce63936d3f3c2b9ec95dd4910ffa8de077f899f0',
    'highs/mip/HighsLpRelaxation.cpp': '328bc4bb67f2a8e89af04f13eb593446e32bee870ca4f3360012308d63144928',
    'highs/io/HighsIO.cpp': '5ee0815ae7f7eb6900ffd1b5f250a0efe9aa14538372949a838e4e26ea4f38e9',
    'highs/io/HighsIO.h': 'f42eb3fa13aaf169b796e2bf8fcda396c7f9cf63c1caa94e383e8b1e2ee4194d',
}
ADMISSION_FORMAT = '\nMIP start solution is %s, objective value is %.12g\n'
COMPLETION_FORMATS = (
    'No continuous variables, so user-supplied values of discrete variables cannot yield feasible solution\n',
    'Attempting to find feasible solution by solving LP for user-supplied values of discrete variables\n',
    'User-supplied values fix only %d / %d discrete variables, so attempt to complete a feasible solution may be expensive\n',
    'Attempting to find feasible solution by solving MIP for user-supplied values of %d / %d discrete variables\n',
    'Highs::optimizeModel() error trying to find feasible solution\n',
)
TIMING_FORMATS = {
    'root_start': 'MIP-Timing: %11.2g - starting evaluate root node\n',
    'root_finish': 'MIP-Timing: %11.2g - completed evaluate root node\n',
    'lp_start': 'MIP-Timing: %11.2g - start first LP solve (with%s basis)\n',
    'lp_finish': 'MIP-Timing: %11.2g - finish first LP solve\n',
}
_NUMBER = r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:e[+-][0-9]{2,3})?'
_ADMISSION = re.compile(r'MIP start solution is (feasible|infeasible), objective value is (' + _NUMBER + ')')
_TIMING = re.compile(r'MIP-Timing: (?P<time> *' + _NUMBER + r') - (?P<event>starting evaluate root node|completed evaluate root node|start first LP solve \(with(?:out)? basis\)|finish first LP solve)')
_TIMING_KINDS = {'starting evaluate root node': 'root_start',
                 'completed evaluate root node': 'root_finish',
                 'start first LP solve (with basis)': 'lp_start',
                 'start first LP solve (without basis)': 'lp_start',
                 'finish first LP solve': 'lp_finish'}
_COUNT = r'[0-9]+[km]?'
_BOUND = r'(?:' + _NUMBER + r'|-?inf)\*?'
_DISPLAY = re.compile(
    r' (?P<source>[ BCFHIJLPRSTUXYZlpuz]) +(?P<nodes>' + _COUNT + r') +(?P<queue>' + _COUNT +
    r') +(?P<leaves>' + _COUNT + r') +(?P<explored>[0-9]+\.[0-9]{2})% +(?P<bound>' + _BOUND +
    r') +(?P<incumbent>' + _BOUND + r') +(?P<gap>Large|inf|[0-9]+\.[0-9]{2}%?) +'
    r'(?P<cuts>[0-9]+) +(?P<in_lp>[0-9]+) +(?P<conflicts>[0-9]+) +(?P<iterations>' + _COUNT +
    r')(?: +(?P<seconds>[0-9]+\.[0-9])s)?')


class AdmissionError(ValueError):
    """A failed gate with JSON-safe evidence for the caller to archive."""
    def __init__(self, reason, evidence):
        super().__init__(reason)
        self.evidence = dict(evidence, passed=False, reason=reason)


def _require(condition, reason, evidence):
    if not condition:
        raise AdmissionError(reason, evidence)


def _source_strings(text):
    """Join adjacent C++ string literals (no compilation or native loading)."""
    # The pinned strings use only the ordinary C escapes handled here.
    literals = r'"(?:[^"\\]|\\.)*"'
    escapes = {'n': '\n', 'r': '\r', 't': '\t', 'a': '\a', 'b': '\b',
               'f': '\f', 'v': '\v', '\\': '\\', '"': '"'}
    return [re.sub(r'\\([nrtabfv\\"])', lambda match: escapes[match[1]],
                   ''.join(literal[1:-1] for literal in re.findall(literals, group)))
            for group in re.findall(r'(?:' + literals + r'\s*)+', text)]


def verify_sources(source_root=None):
    """Verify actual bytes, then the exact source formats used by this parser."""
    root = runtime_path('pristine-source') if source_root is None else Path(source_root)
    contents = {}
    for relative, expected in SOURCE_PINS.items():
        data = (root / relative).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError('Start-admission source pin changed: ' + relative)
        contents[relative] = data.decode('utf-8')
    required = {
        'highs/mip/HighsMipSolverData.cpp': [ADMISSION_FORMAT],
        'highs/lp_data/Highs.cpp': list(COMPLETION_FORMATS),
        'highs/mip/HighsMipSolver.cpp': [TIMING_FORMATS['root_start'], TIMING_FORMATS['root_finish'],
            '\nSolving report\n', '  Repair LPs        %llu (%llu feasible; %llu iterations)\n'],
        'highs/mip/HighsLpRelaxation.cpp': [TIMING_FORMATS['lp_start'], TIMING_FORMATS['lp_finish']],
        'highs/io/HighsIO.cpp': ['%-9s'],
        'highs/io/HighsIO.h': ['WARNING: ', 'ERROR:   '],
    }
    for relative, formats in required.items():
        strings = _source_strings(contents[relative])
        for expected in formats:
            if expected not in strings:
                raise ValueError('Start-admission source format changed: ' + repr(expected))
    return dict(source_commit=SOURCE_COMMIT, source_root=str(root), files_sha256=dict(SOURCE_PINS))


def _fraction(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal, Fraction)):
        raise ValueError('Mapped objective must be a finite numeric value')
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('Mapped objective must be finite')
    if isinstance(value, Decimal) and not value.is_finite():
        raise ValueError('Mapped objective must be finite')
    result = Fraction(value)
    if abs(result) > Fraction(sys.float_info.max):
        raise ValueError('Mapped objective exceeds finite binary64 range')
    return result


def _power10(exponent):
    return Fraction(10 ** exponent) if exponent >= 0 else Fraction(1, 10 ** -exponent)


def _printed_interval(token):
    """Exact round-to-nearest, ties-to-even interval for the source's %.12g.

    Trailing zeros are omitted by %g. A printed power of ten has a smaller
    preceding spacing, so a symmetric relative tolerance would over-admit.
    Zero can only result from zero with significant-digit formatting.
    """
    if len(token) > 64 or re.fullmatch(_NUMBER, token) is None:
        raise ValueError('Malformed start objective token')
    try:
        decimal = Decimal(token)
    except InvalidOperation as exc:
        raise ValueError('Malformed start objective token') from exc
    if not decimal.is_finite() or not -324 <= decimal.adjusted() <= 308:
        raise ValueError('Nonfinite or out-of-range start objective token')
    digits = ''.join(map(str, decimal.as_tuple().digits)).rstrip('0') or '0'
    if len(digits) > 12:
        raise ValueError('Start objective is not a source %.12g token')
    sign = '-' if decimal.is_signed() else ''
    exponent = decimal.adjusted()
    if not decimal:
        canonical = sign + '0'
    elif exponent < -4 or exponent >= 12:
        canonical = sign + digits[0] + ('.' + digits[1:] if len(digits) > 1 else '') + 'e' + format(exponent, '+03d')
    else:
        canonical = format(decimal, 'f')
        if '.' in canonical:
            canonical = canonical.rstrip('0').rstrip('.')
    if token != canonical:
        raise ValueError('Start objective is not a canonical source %.12g token')
    value = Fraction(decimal)
    if not value:
        return value, value, True
    magnitude = abs(value)
    step = _power10(exponent - 11)
    preceding_step = step / 10 if magnitude == _power10(exponent) else step
    low, high = magnitude - preceding_step / 2, magnitude + step / 2
    if value < 0:
        low, high = -high, -low
    inclusive = int(magnitude / step) % 2 == 0
    return low, high, inclusive


def _line(number, text, **fields):
    return dict(line_number=number, line=text, **fields)


def _completion_match(line):
    prefixes = ('', '', 'WARNING: ', '', 'ERROR:   ')
    for index, (fmt, prefix) in enumerate(zip(COMPLETION_FORMATS, prefixes)):
        pattern = re.escape(prefix + fmt.rstrip('\n')).replace('%d', r'[0-9]+')
        if re.fullmatch(pattern, line):
            return index
    return None


def check_admission(text, objective, *, source_root=None):
    """Require one exact feasible admission, matching objective and clean order.

    Pass the untouched CLI log and independently recomputed mapped objective.
    Returns JSON-safe line/order/timing evidence; raises AdmissionError on a
    failed gate, with the same available evidence in exception.evidence.
    Profiling timestamps are reported only when actually logged. Progress-row
    observations are not substituted for precise root or first-LP timestamps.
    """
    if not isinstance(text, str):
        raise ValueError('Raw CLI log must be text')
    evidence = dict(schema='projected-start-cli-admission-v1', passed=False,
        raw_log_sha256=hashlib.sha256(text.encode('utf-8')).hexdigest(),
        raw_log_bytes=len(text.encode('utf-8')), raw_log_mutated=False,
        warning_suppression_added=False, admission_only=True,
        ordinary_later_repair_allowed=True, initial_completion_diagnostics=[],
        later_completion_diagnostics=[], unfiltered_diagnostics=[], events={})
    try:
        evidence['source_identity'] = verify_sources(source_root)
        exact_objective = _fraction(objective)
    except (ValueError, OSError) as exc:
        raise AdmissionError(str(exc), evidence) from exc
    evidence['mapped_objective_exact'] = str(exact_objective)
    lines = text.splitlines()
    admissions, reports, progress, completions = [], [], [], []
    for number, line in enumerate(lines, 1):
        if re.search(r'\bmip\s+start\s+solution\b', line, re.I):
            match = _ADMISSION.fullmatch(line)
            _require(match is not None, 'Unapproved or near-match MIP start diagnostic', dict(evidence, offending_line=_line(number, line)))
            admissions.append(_line(number, line, feasible=match[1] == 'feasible', objective_token=match[2]))
        completion = _completion_match(line)
        if completion is not None or any(marker in line.lower() for marker in
                ('user-supplied values', 'attempt to complete a feasible solution', 'error trying to find feasible solution')):
            completions.append(_line(number, line, source_format_index=completion, exact_source_match=completion is not None))
        if re.search(r'\b(?:warning|error|ignored|dropped)\b', line, re.I):
            evidence['unfiltered_diagnostics'].append(_line(number, line))
        if line == 'Solving report':
            reports.append(_line(number, line))
        timing = _TIMING.fullmatch(line)
        if timing:
            seconds = float(timing['time'])
            if math.isfinite(seconds) and seconds >= 0 and timing['time'] == format(seconds, '.2g').rjust(11):
                kind = _TIMING_KINDS[timing['event']]
                evidence['events'].setdefault(kind, _line(number, line, seconds=seconds, kind=kind))
        display = _DISPLAY.fullmatch(line)
        if display:
            fields = display.groupdict()
            observation = _line(number, line, **fields)
            progress.append(observation)
            evidence['events'].setdefault('first_progress', observation)
            if fields['nodes'] == '0':
                evidence['events'].setdefault('first_root_progress', observation)
            if fields['iterations'] != '0':
                evidence['events'].setdefault('first_progress_with_lp_iterations', observation)
            if fields['incumbent'].rstrip('*') not in ('inf', '-inf'):
                evidence['events'].setdefault('first_incumbent_progress', observation)
    evidence['admission_candidates'] = admissions
    evidence['solve_reports'] = reports
    _require(len(admissions) == 1, 'Require exactly one MIP start admission diagnostic', evidence)
    admission = admissions[0]
    evidence['admission'] = admission
    evidence['initial_incumbent'] = admission
    cutoff = admission['line_number']
    evidence['initial_completion_diagnostics'] = [entry for entry in completions if entry['line_number'] < cutoff]
    evidence['later_completion_diagnostics'] = [entry for entry in completions if entry['line_number'] > cutoff]
    _require(not evidence['initial_completion_diagnostics'], 'Initial start completion or discard diagnostic before admission', evidence)
    _require(admission['feasible'], 'MIP start is infeasible', evidence)
    _require(len(reports) == 1 and reports[0]['line_number'] > cutoff, 'Require one top-level solve report after admission', evidence)
    before = [event for event in evidence['events'].values() if event['line_number'] < cutoff]
    _require(not before, 'MIP search or LP event precedes start admission', dict(evidence, pre_admission_search_events=before))
    try:
        low, high, inclusive = _printed_interval(admission['objective_token'])
    except ValueError as exc:
        raise AdmissionError(str(exc), evidence) from exc
    evidence['objective_interval'] = dict(lower_exact=str(low), upper_exact=str(high), endpoints_inclusive=inclusive,
        significant_digits=12, rounding='nearest_ties_to_even', added_tolerance=0)
    matches = low <= exact_objective <= high if inclusive else low < exact_objective < high
    _require(matches, 'Mapped objective lies outside printed start objective rounding interval', evidence)
    # The admission message itself has no clock field. Preserve the closest
    # emitted clocks rather than inventing an exact admission time.
    clocks = []
    for number, line in enumerate(lines, 1):
        match = re.fullmatch(r'MIP-Timing: ( *' + _NUMBER + r') - .+', line)
        if match and math.isfinite(float(match[1])) and float(match[1]) >= 0 and match[1] == format(float(match[1]), '.2g').rjust(11):
            clocks.append(_line(number, line, seconds=float(match[1])))
    evidence['admission_timing'] = dict(exact_seconds=None,
        preceding_clock=next((entry for entry in reversed(clocks) if entry['line_number'] < cutoff), None),
        following_clock=next((entry for entry in clocks if entry['line_number'] > cutoff), None),
        qualification='Nearest emitted profiling observations; no exact admission timestamp is logged')
    evidence['event_order'] = sorted([dict(admission, kind='admission'), *[dict(event, kind=kind) for kind, event in evidence['events'].items()],
                                    dict(reports[0], kind='solve_report')], key=lambda event: event['line_number'])
    evidence['passed'] = True
    return evidence
