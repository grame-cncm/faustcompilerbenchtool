#!/usr/bin/env python3
"""
fcexplore-bench - Frontend for fcbenchgraph that generates configuration combinations
Usage: fcexplore-bench.py <pattern> [OPTIONS] [FAUST_OPTIONS]

This tool generates all combinations of Faust compiler options and passes them
to fcbenchgraph.py for benchmarking.

Example:
  fcexplore-bench.py "*.dsp" -lang "cpp ocpp" -ss "0 1 2 3" -fir ""

This will generate 16 configurations (2 lang × 4 ss × 2 fir states) and benchmark
all DSP files matching the pattern with these configurations.
"""

import argparse
import itertools
import subprocess
import sys
from typing import List, Dict


def generate_combinations(options, option_values):
    """Generate all possible combinations of values for the options.

    Following fcexplorer.py logic:
    - If option has empty list [], it becomes [None, ''] (absent or present as flag)
    - If option has values, use them as-is (option always present with one of the values)
    """
    value_combinations = []
    for opt in options:
        if option_values[opt] == []:
            # Empty value means flag option: can be absent (None) or present ('')
            value_combinations.append([None, ''])
        else:
            # Has values: option always present with one of these values
            value_combinations.append(option_values[opt])
    return itertools.product(*value_combinations)


def build_config_string(listopt, combination):
    """Build a configuration string from an option combination.

    Args:
        listopt: List of option names (e.g., ['-lang', '-ss', '-fir'])
        combination: Tuple of values (e.g., ('cpp', '0', None))

    Returns:
        Configuration string (e.g., '-lang cpp -ss 0')
    """
    parts = []

    for opt, val in zip(listopt, combination):
        if val is None:
            # Option is absent
            continue
        elif val == '':
            # Flag option (present without value)
            parts.append(opt)
        else:
            # Option with value
            parts.extend([opt, str(val)])

    return ' '.join(parts)


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog='fcexplore-bench',
        description='Explore Faust compiler options and benchmark with fcbenchgraph',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test different lang values with multiple ss values and optional fir
  %(prog)s "*.dsp" -lang "cpp ocpp" -ss "0 1 2 3" -fir ""

  # Test delay options (mcd always present with different values)
  %(prog)s "reverb.dsp" -lang "cpp ocpp" -mcd "0 4 8"

  # With custom iterations and graph output
  %(prog)s "*.dsp" -lang "cpp" -mcd "0 4" --iterations 500 --graph-output my_bench.png

Faust Option Syntax (same as fcexplorer.py):
  -option "val1 val2 val3"  : Option always present, test with each value (N configs)
  -option "val"             : Option always present with this single value (1 config)
  -option ""                : Flag option, test present or absent (2 configs)

fcbenchgraph Options:
  --iterations, --extension, --no-graph, --graph-output, --dry-run
        """
    )

    parser.add_argument('--iterations', type=int, default=1000,
                       help='Number of benchmark iterations (default: 1000)')
    parser.add_argument('--extension', default='.bench',
                       help='Extension for generated binaries (default: .bench)')
    parser.add_argument('--no-graph', action='store_true',
                       help='Disable graph generation')
    parser.add_argument('--graph-output',
                       help='Custom graph filename')
    parser.add_argument('--results-output',
                       help='Custom results markdown filename')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show generated configurations without running benchmark')

    # Parse known args to separate our options from Faust options
    args, remaining = parser.parse_known_args()

    # First remaining argument must be the file pattern
    if not remaining:
        parser.error("file_pattern is required (e.g., '*.dsp')")

    args.file_pattern = remaining[0]
    args.faust_args = remaining[1:]  # Rest are Faust options

    return args


def parse_faust_options(args_list: List[str]) -> Dict[str, List[str]]:
    """Parse Faust compiler options from arguments.

    Following fcexplorer.py logic exactly:
    - Collect options starting with '-'
    - Next non-option argument is the value(s)
    - If value is split by spaces -> list of values
    - If no value follows -> empty list []

    Args:
        args_list: List of command-line arguments

    Returns:
        Dictionary mapping option names to their values
        e.g., {'-lang': ['cpp', 'ocpp'], '-ss': ['0', '1', '2', '3'], '-fir': []}
    """
    option_values = {}
    current_option = None

    for arg in args_list:
        if arg.startswith('-'):
            # This is an option
            current_option = arg
            option_values[current_option] = []
        else:
            # This is a value for the current option
            if current_option:
                # Split by spaces (shell already removed quotes)
                option_values[current_option] = arg.split()
                current_option = None

    return option_values


def main():
    # Parse arguments
    args = parse_arguments()

    # Parse Faust options
    option_values = parse_faust_options(args.faust_args)

    if not option_values:
        print("Error: No Faust options specified. Please provide at least one option.")
        print("Example: fcexplore-bench.py '*.dsp' -lang 'cpp ocpp' -mcd '0 2 4'")
        return 1

    # Generate all combinations
    listopt = list(option_values.keys())
    combinations = list(generate_combinations(listopt, option_values))

    # Build configuration strings
    configs = []
    for combination in combinations:
        config_str = build_config_string(listopt, combination)
        if config_str:  # Only add non-empty configurations
            configs.append(config_str)

    if not configs:
        print("Error: No configurations generated.")
        return 1

    # Display configurations
    print("=" * 70)
    print("=== CONFIGURATION GENERATOR ===")
    print("=" * 70)
    print(f"File pattern: {args.file_pattern}")
    print(f"Generated {len(configs)} configuration(s):")
    print()

    for i, config in enumerate(configs, 1):
        print(f"  [{i}] {config}")

    print()
    print(f"Benchmark iterations: {args.iterations}")
    print(f"Binary extension: {args.extension}")

    if args.dry_run:
        print()
        print("=== DRY RUN MODE ===")
        print("Not executing benchmark. Use without --dry-run to run.")
        return 0

    print("=" * 70)
    print()

    # Build fcbenchgraph command
    fcbenchgraph_cmd = ['fcbenchgraph.py', args.file_pattern]

    # Add all generated configurations (IMPORTANT: quoted!)
    for config in configs:
        fcbenchgraph_cmd.append(config)  # subprocess will handle quoting

    # Add fcbenchgraph options
    fcbenchgraph_cmd.extend(['--iterations', str(args.iterations)])
    fcbenchgraph_cmd.extend(['--extension', args.extension])

    if args.no_graph:
        fcbenchgraph_cmd.append('--no-graph')

    if args.graph_output:
        fcbenchgraph_cmd.extend(['--graph-output', args.graph_output])

    if args.results_output:
        fcbenchgraph_cmd.extend(['--results-output', args.results_output])

    # Execute fcbenchgraph
    print("Executing fcbenchgraph.py...")
    print()

    try:
        result = subprocess.run(fcbenchgraph_cmd, check=True)
        return result.returncode
    except subprocess.CalledProcessError as e:
        print(f"\nError executing fcbenchgraph: {e}", file=sys.stderr)
        return e.returncode
    except FileNotFoundError:
        print("\nError: fcbenchgraph.py not found. Make sure it's in your PATH.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
