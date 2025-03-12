#!/usr/bin/env python3
"""
Command Line Interface for Circuit Breaker Management

This script provides a CLI for managing and monitoring circuit breakers
in the court data ingestion pipeline.
"""

import argparse
import json
import logging
import sys
from .circuit_breaker_manager import get_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('circuit-breaker-cli')

def list_breakers(args):
    """List all circuit breakers and their states"""
    manager = get_manager(use_redis=not args.in_memory)
    metrics = manager.get_all_metrics()
    
    print("\nCircuit Breaker Status:")
    print("-" * 80)
    
    for name, data in metrics.items():
        print(f"\nBreaker: {name}")
        print(f"State: {data['state']}")
        print(f"Failure Rate: {data['failure_rate']:.2%}")
        print(f"Total Requests: {data['total_count']}")
        print(f"Last State Change: {data['last_state_change']}")
        print("-" * 40)

def show_metrics(args):
    """Show detailed metrics for a specific circuit breaker"""
    manager = get_manager(use_redis=not args.in_memory)
    metrics = manager.get_metrics(args.doc_type, args.stage)
    
    if metrics:
        print("\nDetailed Circuit Breaker Metrics:")
        print("-" * 80)
        print(json.dumps(metrics, indent=2))
    else:
        print(f"No metrics found for {args.doc_type}_{args.stage}")

def reset_breaker(args):
    """Reset a circuit breaker to closed state"""
    manager = get_manager(use_redis=not args.in_memory)
    breaker = manager.get_breaker(args.doc_type, args.stage)
    
    if breaker:
        breaker.set_state('CLOSED')
        print(f"Reset circuit breaker for {args.doc_type}_{args.stage} to CLOSED state")
    else:
        print(f"Circuit breaker not found for {args.doc_type}_{args.stage}")

def main():
    """Main entry point for the circuit breaker CLI"""
    parser = argparse.ArgumentParser(description='Circuit Breaker Management CLI')
    parser.add_argument('--in-memory', action='store_true',
                       help='Use in-memory circuit breakers instead of Redis')
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # List command
    subparsers.add_parser('list', help='List all circuit breakers and their states')
    
    # Metrics command
    metrics_parser = subparsers.add_parser('metrics',
                                         help='Show detailed metrics for a circuit breaker')
    metrics_parser.add_argument('doc_type', help='Document type (e.g., courts, dockets)')
    metrics_parser.add_argument('stage', help='Processing stage (ingestion, vectorization)')
    
    # Reset command
    reset_parser = subparsers.add_parser('reset',
                                       help='Reset a circuit breaker to closed state')
    reset_parser.add_argument('doc_type', help='Document type (e.g., courts, dockets)')
    reset_parser.add_argument('stage', help='Processing stage (ingestion, vectorization)')
    
    args = parser.parse_args()
    
    if args.command == 'list':
        list_breakers(args)
    elif args.command == 'metrics':
        show_metrics(args)
    elif args.command == 'reset':
        reset_breaker(args)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
