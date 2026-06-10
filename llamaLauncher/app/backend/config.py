from typing import Dict, Any, Tuple

# Default configuration profiles
DEFAULT_GPU_OFFLOAD = 99
DEFAULT_CPU_OFFLOAD = 0

def optimize_params(dev_type: str, physical_cores: int, pq_choice: str = "3") -> Dict[str, Any]:
    """
    Optimizes server execution parameters based on hardware and engine.
    Adapts context size dynamically if PolarQuant cache compression is enabled.
    """
    config = {}
    
    # 1. Threads optimization
    config["threads"] = max(1, physical_cores)
    
    # 2. Base Port
    config["port"] = 8080
    
    # 3. NGL (Offloading) based on device type
    if dev_type == "CPU":
        config["ngl"] = DEFAULT_CPU_OFFLOAD
    else:
        config["ngl"] = DEFAULT_GPU_OFFLOAD

    # 4. Adjust context size based on PolarQuant choice
    context_multiplier = 1024  # Base multiplier for context size    
    if pq_choice == "4":
        config["context"] = 32 * context_multiplier  # 32K for Ultra Performance Mode
    elif pq_choice == "1":
        config["context"] = 32 * context_multiplier  # 32K for Performance Mode
    elif pq_choice == "5":
        config["context"] = 24 * context_multiplier  # 24K for Balanced Mode
    elif pq_choice == "6":
        config["context"] = 16 * context_multiplier  # 16K for High Quality Mode
    elif pq_choice == "2":
        config["context"] = 16 * context_multiplier  # 16K for Max Quality Mode
    else:
        config["context"] = 8 * context_multiplier  # 8K for Standard Mode
    return config

def get_polar_quant_flags(pq_choice: str) -> Tuple[str, str]:
    """
    Translates user choice into actual llama-server CLI flags for PolarQuant.
    Returns (flags_string, status_string).
    """
    if pq_choice == "4":
        return "--cache-type-k q3_K --cache-type-v q3_K -fa on", "Enabled (Ultra Performance: Q3_K + Flash Attention)"
    elif pq_choice == "1":
        return "--cache-type-k q4_0 --cache-type-v q4_0 -fa on", "Enabled (Performance: Q4_0 + Flash Attention)"
    elif pq_choice == "5":
        return "--cache-type-k q5_0 --cache-type-v q5_0 -fa on", "Enabled (Balanced: Q5_0 + Flash Attention)"
    elif pq_choice == "6":
        return "--cache-type-k q6_K --cache-type-v q6_K -fa on", "Enabled (High Quality: Q6_K + Flash Attention)"
    elif pq_choice == "2":
        return "--cache-type-k q8_0 --cache-type-v q8_0 -fa on", "Enabled (Max Quality: Q8_0 + Flash Attention)"
    else:
        # Standard Mode
        return "", "Disabled (Standard FP16)"
