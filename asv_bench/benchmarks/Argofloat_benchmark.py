## Argo float benchmark

from datetime import timedelta

import numpy as np

from parcels import AdvectionRK4, FieldSet, JITParticle, ParticleSet, StatusCode, Variable


def ArgoVerticalMovement(particle, fieldset, time):
    driftdepth = 1000  # maximum depth in m
    maxdepth = 2000  # maximum depth in m
    vertical_speed = 0.10  # sink and rise speed in m/s
    cycletime = 10 * 86400  # total time of cycle in seconds
    drifttime = 9 * 86400  # time of deep drift in seconds

    if particle.cycle_phase == 0:
        # Phase 0: Sinking with vertical_speed until depth is driftdepth
        particle_ddepth += vertical_speed * particle.dt
        if particle.depth + particle_ddepth >= driftdepth:
            particle_ddepth = driftdepth - particle.depth
            particle.cycle_phase = 1

    elif particle.cycle_phase == 1:
        # Phase 1: Drifting at depth for drifttime seconds
        particle.drift_age += particle.dt
        if particle.drift_age >= drifttime:
            particle.drift_age = 0  # reset drift_age for next cycle
            particle.cycle_phase = 2

    elif particle.cycle_phase == 2:
        # Phase 2: Sinking further to maxdepth
        particle_ddepth += vertical_speed * particle.dt
        if particle.depth + particle_ddepth >= maxdepth:
            particle_ddepth = maxdepth - particle.depth
            particle.cycle_phase = 3

    elif particle.cycle_phase == 3:
        # Phase 3: Rising with vertical_speed until at surface
        particle_ddepth -= vertical_speed * particle.dt
        # particle.temp = fieldset.temp[time, particle.depth, particle.lat, particle.lon]  # if fieldset has temperature
        if particle.depth + particle_ddepth <= fieldset.mindepth:
            particle_ddepth = fieldset.mindepth - particle.depth
            # particle.temp = 0./0.  # reset temperature to NaN at end of sampling cycle
            particle.cycle_phase = 4

    elif particle.cycle_phase == 4:
        # Phase 4: Transmitting at surface until cycletime is reached
        if particle.cycle_age > cycletime:
            particle.cycle_phase = 0
            particle.cycle_age = 0

    if particle.state == StatusCode.Evaluate:
        particle.cycle_age += particle.dt  # update cycle_age


class ArgoFloatJIT:
    def setup(self):
        xdim = ydim = zdim = 2

        dimensions = {
            "lon": "lon",
            "lat": "lat",
            "depth": "depth",
        }
        data = {
            "U": np.ones((xdim, ydim, zdim), dtype=np.float32),
            "V": np.zeros((xdim, ydim, zdim), dtype=np.float32),
        }
        data["U"][:, :, 0] = 0.0
        fieldset = FieldSet.from_data(data, dimensions, mesh="flat", transpose=True)
        fieldset.mindepth = fieldset.U.depth[0]

        # Define a new Particle type including extra Variables
        self.ArgoParticle = JITParticle.add_variables(
            [
                # Phase of cycle:
                # init_descend=0,
                # drift=1,
                # profile_descend=2,
                # profile_ascend=3,
                # transmit=4
                Variable("cycle_phase", dtype=np.int32, initial=0.0),
                Variable("cycle_age", dtype=np.float32, initial=0.0),
                Variable("drift_age", dtype=np.float32, initial=0.0),
                # if fieldset has temperature
                # Variable('temp', dtype=np.float32, initial=np.nan),
            ]
        )

        self.pset = ParticleSet(fieldset=fieldset, pclass=ArgoParticle, lon=[0], lat=[0], depth=[0])

        # combine Argo vertical movement kernel with built-in Advection kernel
        self.kernels = [ArgoVerticalMovement, AdvectionRK4]

    def time_run_single_timestep(self):
        self.pset.execute(AdvectionRK4, runtime=timedelta(seconds=1 * 30), dt=timedelta(seconds=30))
