#!/usr/bin/env python3
"""
Compare performance metrics across different routing algorithms (Dijkstra, PSO, Hybrid)
Generates comparison plots for all scenarios
"""

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import os

class ComparisonPlotter:
    def __init__(self, results_base_dir="/home/duy/sdn_qos_project/results"):
        self.results_dir = Path(results_base_dir)
        self.algorithms = ["dijkstra", "pso", "hybrid"]
        
        # Scenario configurations
        self.scenarios = {
            # "sc1": {
            #     "name": "Scenario 1: Baseline Path Quality",
            #     "file": "sc1_baseline.csv",
            #     "output_dir": "sc1"
            # },
            "sc2": {
                "name": "Scenario 2: Heavy Congestion",
                "file": "sc2_congestion.csv",
                "output_dir": "sc2"
            },
            # "sc3": {
            #     "name": "Scenario 3: Failure + Congestion + Recovery",
            #     "file": "sc3_failure_phase2_failure.csv",
            #     "output_dir": "sc3"
            # }
        }

    def load_data(self, scenario_key):
       
        data = {}
        scenario_info = self.scenarios[scenario_key]
        
        for algo in self.algorithms:
            file_path = self.results_dir / algo / scenario_info["file"]
            try:
                df = pd.read_csv(file_path)
                data[algo] = df
                print(f"✅ Loaded {algo}: {file_path}")
            except FileNotFoundError:
                print(f"❌ Not found: {file_path}")
        
        return data

    def create_output_dir(self, scenario_key):
      
        output_path = self.results_dir / self.scenarios[scenario_key]["output_dir"]
        output_path.mkdir(exist_ok=True, parents=True)
        return output_path

    def plot_metrics(self, scenario_key):
      
        data = self.load_data(scenario_key)
        
        if not data:
            print(f"⚠️  No data found for {scenario_key}")
            return
        
        output_path = self.create_output_dir(scenario_key)
        scenario_name = self.scenarios[scenario_key]["name"]
        
        print(f"\n📊 Creating plots for {scenario_name}...")
        
        # Create figure with 4 subplots (2x2 grid)
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle(f"{scenario_name} - Algorithm Comparison", fontsize=16, fontweight='bold')
        
        # Define metrics to plot
        metrics = [
            ("throughput_Mbps", "Throughput (Mbps)", axes[0, 0]),
            ("delay_ms", "Delay (ms)", axes[0, 1]),
            ("jitter_ms", "Jitter (ms)", axes[1, 0]),
            ("loss", "Packet Loss Rate", axes[1, 1])
        ]
        
        # Define colors for each algorithm
        colors = {
            "dijkstra": "#FF6B6B",  # Red
            "pso": "#4ECDC4",       # Teal
            "hybrid": "#D145CC"     # Blue
        }
        
        # Plot each metric
        for metric_col, metric_label, ax in metrics:
            for algo in self.algorithms:
                if algo not in data:
                    continue
                
                df = data[algo]
                time_col = "time_s"
                
                # Handle missing columns
                if metric_col not in df.columns or time_col not in df.columns:
                    print(f"⚠️  Missing column {metric_col} or {time_col} in {algo}")
                    continue
                
                ax.plot(df[time_col], df[metric_col], 
                       label=algo.upper(), 
                       color=colors.get(algo, "black"),
                       linewidth=2,
                       alpha=0.8)
            
            ax.set_xlabel("Time (seconds)", fontsize=11, fontweight='bold')
            ax.set_ylabel(metric_label, fontsize=11, fontweight='bold')
            ax.set_title(metric_label, fontsize=12, fontweight='bold')
            ax.grid(True, alpha=0.3, linestyle='--')
            ax.legend(loc='best', fontsize=10, framealpha=0.9)
            ax.set_facecolor('#f8f9fa')
        
        plt.tight_layout()
        
        # Save the figure
        output_file = output_path / f"{scenario_key}_comparison.png"
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"💾 Saved: {output_file}")
        plt.close()

    def create_individual_plots(self, scenario_key):
        
        data = self.load_data(scenario_key)
        
        if not data:
            print(f"⚠️  No data found for {scenario_key}")
            return
        
        output_path = self.create_output_dir(scenario_key)
        scenario_name = self.scenarios[scenario_key]["name"]
        
        # Define metrics
        metrics = [
            ("throughput_Mbps", "Throughput (Mbps)", "throughput"),
            ("delay_ms", "Delay (ms)", "delay"),
            ("jitter_ms", "Jitter (ms)", "jitter"),
            ("loss", "Packet Loss Rate", "loss")
        ]
        
        colors = {
            "dijkstra": "#FF6B6B",
            "pso": "#4ECDC4",
            "hybrid": "#D145CC"
        }
        
        for metric_col, metric_label, metric_name in metrics:
            fig, ax = plt.subplots(figsize=(14, 8))
            
            for algo in self.algorithms:
                if algo not in data:
                    continue
                
                df = data[algo]
                time_col = "time_s"
                
                if metric_col not in df.columns or time_col not in df.columns:
                    continue
                
                ax.plot(df[time_col], df[metric_col], 
                       label=algo.upper(), 
                       color=colors.get(algo, "black"),
                       linewidth=2.5,
                       marker='o',
                       markersize=3,
                       alpha=0.8)
            
            ax.set_xlabel("Time (seconds)", fontsize=12, fontweight='bold')
            ax.set_ylabel(metric_label, fontsize=12, fontweight='bold')
            ax.set_title(f"{scenario_name}\n{metric_label} Comparison", 
                        fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3, linestyle='--')
            ax.legend(loc='best', fontsize=11, framealpha=0.95)
            ax.set_facecolor('#f8f9fa')
            
            plt.tight_layout()
            
            # Save individual plot
            output_file = output_path / f"{scenario_key}_{metric_name}.png"
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            print(f"💾 Saved: {output_file}")
            plt.close()

    def create_statistics_table(self, scenario_key):
        """Create statistics table for all metrics"""
        data = self.load_data(scenario_key)
        
        if not data:
            return
        
        output_path = self.create_output_dir(scenario_key)
        
        print(f"\n📈 Statistics for {scenario_key}:")
        
        # Metrics to analyze
        metrics = ["throughput_Mbps", "delay_ms", "jitter_ms", "loss"]
        
        # Create statistics table
        stats_data = {}
        
        for algo in self.algorithms:
            if algo not in data:
                continue
            
            df = data[algo]
            stats_data[algo] = {}
            
            for metric in metrics:
                if metric in df.columns:
                    stats_data[algo][metric] = {
                        "mean": df[metric].mean(),
                        "std": df[metric].std(),
                        "min": df[metric].min(),
                        "max": df[metric].max()
                    }
        
        # Print and save statistics
        stats_text = f"Statistics for {self.scenarios[scenario_key]['name']}\n"
        stats_text += "=" * 80 + "\n\n"
        
        for metric in metrics:
            stats_text += f"\n{metric.upper()}\n"
            stats_text += "-" * 80 + "\n"
            stats_text += f"{'Algorithm':<15} {'Mean':>15} {'Std Dev':>15} {'Min':>15} {'Max':>15}\n"
            stats_text += "-" * 80 + "\n"
            
            for algo in self.algorithms:
                if algo in stats_data and metric in stats_data[algo]:
                    s = stats_data[algo][metric]
                    stats_text += f"{algo.upper():<15} {s['mean']:>15.4f} {s['std']:>15.4f} {s['min']:>15.4f} {s['max']:>15.4f}\n"
        
        print(stats_text)
        
        # Save statistics to file
        stats_file = output_path / f"{scenario_key}_statistics.txt"
        with open(stats_file, 'w') as f:
            f.write(stats_text)
        print(f" Saved statistics: {stats_file}")

    def run_all(self):
        """Generate all comparison plots for all scenarios"""
        print("\n" + "="*80)
        print(" ALGORITHM COMPARISON ANALYSIS")
        print("="*80)
        
        for scenario_key in [ "sc2"]:
            print(f"\n{'='*80}")
            print(f"Processing {scenario_key}...")
            print('='*80)
            
            # Create combined plot
            self.plot_metrics(scenario_key)
            
            # Create individual plots
            self.create_individual_plots(scenario_key)
            
            # Create statistics
            self.create_statistics_table(scenario_key)
        
        print("\n" + "="*80)
        print("ALL COMPARISON PLOTS GENERATED SUCCESSFULLY")
        print("="*80)
        print("\nOutput locations:")
        for scenario_key in ["sc1", "sc2", "sc3"]:
            output_path = self.results_dir / self.scenarios[scenario_key]["output_dir"]
            print(f"  {scenario_key}: {output_path}")


if __name__ == "__main__":
    plotter = ComparisonPlotter()
    plotter.run_all()
