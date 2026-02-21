"""
NHL Adapter Demo
----------------
Demonstrates how to use the NHLAdapter to fetch real NHL play-by-play event streams.
Simulates live streaming environment with game event data.

Usage:
    python tools/demo_nhl.py --game 2024020001
    python tools/demo_nhl.py --season 2024 --game-num 50
"""
import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from adapters.nhl.ingestion_nhl import NHLAdapter
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


def main():
    parser = argparse.ArgumentParser(description='Fetch NHL play-by-play events from NHL Stats API')
    parser.add_argument(
        '--game',
        type=str,
        default=None,
        help='Full game ID (e.g., "2024020001" for first game of 2024-25 season)'
    )
    parser.add_argument(
        '--season',
        type=int,
        default=2024,
        help='Season starting year (default: 2024 for 2024-25)'
    )
    parser.add_argument(
        '--game-num',
        type=int,
        default=1,
        help='Game number (default: 1)'
    )
    parser.add_argument(
        '--game-type',
        type=str,
        default="02",
        choices=["02", "03"],
        help='Game type: 02=regular season, 03=playoffs (default: 02)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=20,
        help='Number of events to display'
    )
    
    args = parser.parse_args()
    
    # Build game ID
    if args.game:
        game_id = args.game
    else:
        game_id = NHLAdapter.build_game_id(args.season, args.game_type, args.game_num)
    
    console.print("\n[bold cyan]🏒 NHL Play-by-Play Event Stream Demo[/bold cyan]")
    console.print(f"Game ID: {game_id}\n")
    
    try:
        # Initialize the adapter
        console.print("[yellow]Initializing NHL Adapter...[/yellow]")
        adapter = NHLAdapter(game_id=game_id)
        
        # Fetch and process data
        console.print("[yellow]Fetching play-by-play event stream...[/yellow]")
        df = adapter.fetch_data()
        
        # Display results
        console.print(f"\n[green]✓ Successfully fetched {len(df)} game events[/green]\n")
        
        # Get actual column names from dataframe
        available_cols = list(df.columns)
        
        # Show event stream table
        table = Table(title=f"NHL Event Stream: Game {game_id} (First {args.limit} events)")
        
        # Prioritize display columns (try reconciled names first, then raw names)
        preferred_cols = [
            ("Event Type", "event_type_code"),
            ("Period", "period_num"),
            ("Time", "period_time_elapsed"),
            ("Player Name", "player_name_full"),
            ("Team", "team_abbrev"),
        ]
        
        display_cols = []
        for gold, raw in preferred_cols:
            if gold in available_cols:
                display_cols.append(gold)
            elif raw in available_cols:
                display_cols.append(raw)
        
        # If no preferred columns found, use first 5 columns
        if not display_cols:
            display_cols = available_cols[:5]
        
        for col in display_cols:
            table.add_column(col.replace("_", " ").title(), style="cyan", no_wrap=False)
        
        for row in df.head(args.limit).iter_rows(named=True):
            table.add_row(*[str(row.get(col, "N/A"))[:40] for col in display_cols])
        
        console.print(table)
        
        # Show event type breakdown
        console.print("\n[bold magenta]📊 Event Type Breakdown:[/bold magenta]")
        
        event_col = None
        if "Event Type" in df.columns:
            event_col = "Event Type"
        elif "event_type_code" in df.columns:
            event_col = "event_type_code"
        
        if event_col:
            event_counts = df[event_col].value_counts()
            event_names = {
                "SHOT": "Shots",
                "GOAL": "Goals",
                "HIT": "Hits",
                "PENALTY": "Penalties",
                "FACEOFF": "Faceoffs",
                "BLOCKED_SHOT": "Blocked Shots",
                "MISSED_SHOT": "Missed Shots",
                "GIVEAWAY": "Giveaways",
                "TAKEAWAY": "Takeaways"
            }
            for row in event_counts.iter_rows(named=True):
                event_type = row.get(event_col)
                count = row.get("count")
                event_name = event_names.get(event_type, event_type)
                console.print(f"  {event_name}: {count}")
        
        # Show semantic reconciliation results
        if adapter.last_resolutions:
            console.print("\n[bold magenta]🔧 Semantic Reconciliation Results:[/bold magenta]")
            for resolution in adapter.last_resolutions[:8]:
                console.print(
                    f"  [yellow]{resolution['raw_field']}[/yellow] → "
                    f"[green]{resolution['target_field']}[/green] "
                    f"(confidence: {resolution['confidence']:.2%})"
                )
        
        console.print(f"\n[bold blue]📋 Pipeline Lineage:[/bold blue]")
        for entry in adapter.lineage[-8:]:  # Show last 8 stages
            console.print(f"  • {entry['stage']} at {entry['timestamp']}")
        
        # Export audit log
        audit_path = f"data/nhl_game_{game_id}_audit.json"
        adapter.export_audit_log(audit_path)
        console.print(f"\n[green]✓ Audit log exported to: {audit_path}[/green]")
        
        # Show data statistics
        console.print("\n[bold cyan]📊 Data Statistics:[/bold cyan]")
        stats_table = Table()
        stats_table.add_column("Metric", style="yellow")
        stats_table.add_column("Value", style="green")
        
        stats_table.add_row("Total Events", str(len(df)))
        stats_table.add_row("Game ID", game_id)
        
        if event_col and event_col in df.columns:
            event_series = df[event_col]
            stats_table.add_row("Event Types", str(event_series.n_unique()))
            if "GOAL" in event_series.to_list():
                goals = (event_series == "GOAL").sum()
                stats_table.add_row("Goals", str(goals))
            if "SHOT" in event_series.to_list():
                shots = (event_series == "SHOT").sum()
                stats_table.add_row("Shots", str(shots))
        
        console.print(stats_table)
        
        console.print("\n[bold green]✓ Demo completed successfully![/bold green]\n")
        
    except Exception as e:
        console.print(f"\n[bold red]Error: {str(e)}[/bold red]\n")
        import traceback
        console.print(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
