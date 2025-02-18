# Benchmarking

Parcels comes with an [asv](https://asv.readthedocs.io/en/latest/) benchmarking suite to monitor the performance of the project over it's lifespan.

The benchmarking is run in CI using GitHub Actions (similar to other projects like xarray, scikit-image, and pandas), using a ratio to determine performance regressions instead of raw outputs. More on the reliability of benchmarking in CI can be seen at [this blog post](https://labs.quansight.org/blog/2021/08/github-actions-benchmarks). Due to the reliance of CI for benchmarking, the benchmarks are small such that they test the core functionality of Parcels. Large scale simulation benchmarking is an avenue for future development.

## Setup

The asv benchmarks require these dependencies:

`conda install -c conda-forge asv>0.6 libmambapy<2 conda-build`

Progress on compatibility of asv with libmambapy 2 is documented at [this issue](https://github.com/airspeed-velocity/asv/issues/1438).

## Running the benchmarks

The benchmarks are located in the `asv_bench` folder can be run locally using the following commands:

```bash
cd asv_bench
asv run
```
