#!/usr/bin/env python
# Usage
#   ./version-chart.py <chart-name> <version>

import os
import yaml
import sys


def set_chart_version(name, version):
    """
    Update the verison and appVersion in Chart.yaml for the given Helm chart
    """
    
    chart_file = os.path.join(name, 'Chart.yaml')
    with open(chart_file) as f:
        chart = yaml.safe_load(f)

    chart['version'] = version
    # appVersion and version are always identical for now
    chart['appVersion'] = version

    with open(chart_file, 'w') as fout:
        yaml.dump(chart, fout)


if __name__ == "__main__":

    _, name, version = sys.argv

    set_chart_version(name, version)

    