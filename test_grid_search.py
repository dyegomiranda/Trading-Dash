#!/usr/bin/env python3
"""
Simple test to verify grid search functionality in walkforward module
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from backtest.walkforward import grid_search_walk_forward, GridSearchResult
from backtest.engine import BacktestConfig
from data.providers import DemoDataProvider

def test_grid_search_basic():
    """Test that grid search runs without errors"""
    print("Testing grid search functionality...")

    # Create a simple config
    config = BacktestConfig(
        start="2022-01-03",
        end="2022-12-30",
        initial_cash=10000.0,
        top_n=5,
        min_score=0.0,
        rebalance="M",
        universe=["PETR4.SA", "VALE3.SA", "ITUB4.SA"],  # Small universe for fast test
        use_point_in_time_fundamentals=False,
        min_daily_volume_brl=0.0,
        max_adv_order_pct=0.0
    )

    # Create a very small parameter grid for testing
    param_grid = {
        "top_n": [3, 5],
        "min_score": [0.0, 10.0],
        "rebalance": ["M"],
        "core_weight": [0.7]
    }

    # Use demo provider for consistent, fast results
    provider = DemoDataProvider()

    # Execute grid search
    result: GridSearchResult = grid_search_walk_forward(
        provider=provider,
        base_config=config,
        param_grid=param_grid,
        fraction=0.7,
        max_combinations=4,  # Limit to 4 combinations for quick test
        risk_free_rate=0.115
    )

    # Verify results
    assert isinstance(result, GridSearchResult), "Result should be GridSearchResult"
    assert isinstance(result.best_params, dict), "Best params should be dict"
    assert isinstance(result.best_sharpe, float), "Best sharpe should be float"
    assert result.best_wf_report is not None, "Best walkforward report should not be None"
    assert len(result.all_results) > 0, "Should have results"

    print(f"✓ Grid search completed successfully")
    print(f"  Best params: {result.best_params}")
    print(f"  Best Sharpe: {result.best_sharpe:.4f}")
    print(f"  Number of combinations tested: {len(result.all_results)}")

    return True

def test_grid_search_empty():
    """Test grid search with empty parameter grid"""
    print("\nTesting grid search with empty parameter grid...")

    config = BacktestConfig(
        start="2022-01-03",
        end="2022-12-30",
        initial_cash=10000.0,
        top_n=5,
        min_score=0.0,
        rebalance="M",
        universe=["PETR4.SA"],
        use_point_in_time_fundamentals=False,
        min_daily_volume_brl=0.0,
        max_adv_order_pct=0.0
    )

    provider = DemoDataProvider()

    # Execute with empty grid
    result: GridSearchResult = grid_search_walk_forward(
        provider=provider,
        base_config=config,
        param_grid={},  # Empty grid
        fraction=0.7
    )

    # Should still return a valid result (equivalent to normal walk-forward)
    assert isinstance(result, GridSearchResult), "Result should be GridSearchResult"
    assert result.best_params == {}, "Best params should be empty dict"
    assert isinstance(result.best_sharpe, float), "Best sharpe should be float"
    assert result.best_wf_report is not None, "Best walkforward report should not be None"

    print(f"✓ Empty grid search completed successfully")
    print(f"  Best Sharpe: {result.best_sharpe:.4f}")

    return True

if __name__ == "__main__":
    try:
        test_grid_search_basic()
        test_grid_search_empty()
        print("\n🎉 All tests passed! Grid search implementation is working correctly.")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)