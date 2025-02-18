from datetime import timedelta

import numpy as np

from parcels import AdvectionRK4, FieldSet, ParticleSet, ScipyParticle


def time_advection2d():
    """Flat 2D zonal flow that increases linearly with depth from 0 m/s to 1 m/s.

    Time-taking variant.
    """
    xdim = ydim = zdim = 2
    npart = 11

    dimensions = {
        "lon": np.linspace(0.0, 1e4, xdim, dtype=np.float32),
        "lat": np.linspace(0.0, 1e4, ydim, dtype=np.float32),
        "depth": np.linspace(0.0, 1.0, zdim, dtype=np.float32),
    }
    data = {
        "U": np.ones((xdim, ydim, zdim), dtype=np.float32),
        "V": np.zeros((xdim, ydim, zdim), dtype=np.float32),
    }
    data["U"][:, :, 0] = 0.0
    fieldset = FieldSet.from_data(data, dimensions, mesh="flat", transpose=True)

    pset = ParticleSet(
        fieldset,
        pclass=ScipyParticle,
        lon=np.zeros(npart),
        lat=np.zeros(npart) + 1e2,
        depth=np.linspace(0, 1, npart),
    )

    pset.execute(AdvectionRK4, runtime=timedelta(hours=2), dt=timedelta(seconds=30))
    assert np.allclose(pset.depth * pset.time, pset.lon, atol=1.0e-1)


def peakmem_advection2d():
    """Flat 2D zonal flow that increases linearly with depth from 0 m/s to 1 m/s.

    Peak-Mem-taking variant.
    """
    xdim = ydim = zdim = 2
    npart = 11

    dimensions = {
        "lon": np.linspace(0.0, 1e4, xdim, dtype=np.float32),
        "lat": np.linspace(0.0, 1e4, ydim, dtype=np.float32),
        "depth": np.linspace(0.0, 1.0, zdim, dtype=np.float32),
    }
    data = {
        "U": np.ones((xdim, ydim, zdim), dtype=np.float32),
        "V": np.zeros((xdim, ydim, zdim), dtype=np.float32),
    }
    data["U"][:, :, 0] = 0.0
    fieldset = FieldSet.from_data(data, dimensions, mesh="flat", transpose=True)

    pset = ParticleSet(
        fieldset,
        pclass=ScipyParticle,
        lon=np.zeros(npart),
        lat=np.zeros(npart) + 1e2,
        depth=np.linspace(0, 1, npart),
    )

    pset.execute(AdvectionRK4, runtime=timedelta(hours=2), dt=timedelta(seconds=30))
    assert np.allclose(pset.depth * pset.time, pset.lon, atol=1.0e-1)
