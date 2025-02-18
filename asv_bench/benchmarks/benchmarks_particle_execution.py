from datetime import timedelta

import numpy as np

from parcels import AdvectionRK4, FieldSet, JITParticle, ParticleSet, ScipyParticle


class ParticleExecutionJIT:
    def setup(self):
        xdim = ydim = zdim = 2
        npart = 1_000

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

        self.pset = ParticleSet(
            fieldset,
            pclass=JITParticle,
            lon=np.zeros(npart),
            lat=np.zeros(npart) + 1e2,
            depth=np.linspace(0, 1, npart),
        )
        # trigger compilation
        self.pset.execute(AdvectionRK4, runtime=0, dt=timedelta(seconds=30))

    def time_run_single_timestep(self):
        self.pset.execute(AdvectionRK4, runtime=timedelta(seconds=1 * 30), dt=timedelta(seconds=30))

    def time_run_many_timesteps(self):
        self.pset.execute(AdvectionRK4, runtime=timedelta(seconds=100 * 30), dt=timedelta(seconds=30))


class ParticleExecutionScipy:
    def setup(self):
        xdim = ydim = zdim = 2
        npart = 1_000

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

        self.pset = ParticleSet(
            fieldset,
            pclass=ScipyParticle,
            lon=np.zeros(npart),
            lat=np.zeros(npart) + 1e2,
            depth=np.linspace(0, 1, npart),
        )

    def time_run_single_timestep(self):
        self.pset.execute(AdvectionRK4, runtime=timedelta(seconds=1 * 30), dt=timedelta(seconds=30))

    def time_run_many_timesteps(self):
        self.pset.execute(AdvectionRK4, runtime=timedelta(seconds=100 * 30), dt=timedelta(seconds=30))
