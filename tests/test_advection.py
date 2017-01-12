from parcels import Grid, ParticleSet, ScipyParticle, JITParticle
from parcels import AdvectionEE, AdvectionRK4, AdvectionRK45
import numpy as np
import pytest
import math
from datetime import timedelta as delta
from argparse import ArgumentParser


ptype = {'scipy': ScipyParticle, 'jit': JITParticle}
kernel = {'EE': AdvectionEE, 'RK4': AdvectionRK4, 'RK45': AdvectionRK45}

# Some constants
f = 1.e-4
u_0 = 0.3
u_g = 0.04
gamma = 1/(86400. * 2.89)
gamma_g = 1/(86400. * 28.9)


@pytest.fixture
def lon(xdim=200):
    return np.linspace(-170, 170, xdim, dtype=np.float32)


@pytest.fixture
def lat(ydim=100):
    return np.linspace(-80, 80, ydim, dtype=np.float32)


@pytest.mark.parametrize('mode', ['scipy', 'jit'])
def test_advection_zonal(lon, lat, mode, npart=10):
    """ Particles at high latitude move geographically faster due to
        the pole correction in `GeographicPolar`.
    """
    U = np.ones((lon.size, lat.size), dtype=np.float32)
    V = np.zeros((lon.size, lat.size), dtype=np.float32)
    grid = Grid.from_data(U, lon, lat, V, lon, lat, mesh='spherical')

    pset = ParticleSet(grid, pclass=ptype[mode],
                       lon=np.zeros(npart, dtype=np.float32) + 20.,
                       lat=np.linspace(0, 80, npart, dtype=np.float32))
    pset.execute(AdvectionRK4, endtime=delta(hours=2), dt=delta(seconds=30))
    assert (np.diff(np.array([p.lon for p in pset])) > 1.e-4).all()


@pytest.mark.parametrize('mode', ['scipy', 'jit'])
def test_advection_meridional(lon, lat, mode, npart=10):
    """ Particles at high latitude move geographically faster due to
        the pole correction in `GeographicPolar`.
    """
    U = np.zeros((lon.size, lat.size), dtype=np.float32)
    V = np.ones((lon.size, lat.size), dtype=np.float32)
    grid = Grid.from_data(U, lon, lat, V, lon, lat, mesh='spherical')

    pset = ParticleSet(grid, pclass=ptype[mode],
                       lon=np.linspace(-60, 60, npart, dtype=np.float32),
                       lat=np.linspace(0, 30, npart, dtype=np.float32))
    delta_lat = np.diff(np.array([p.lat for p in pset]))
    pset.execute(AdvectionRK4, endtime=delta(hours=2), dt=delta(seconds=30))
    assert np.allclose(np.diff(np.array([p.lat for p in pset])), delta_lat, rtol=1.e-4)


def periodicgrid(xdim, ydim, uvel, vvel):
    lon = np.linspace(0., 1., xdim+1, dtype=np.float32)[1:]  # don't include both 0 and 1, for periodic b.c.
    lat = np.linspace(0., 1., ydim+1, dtype=np.float32)[1:]

    U = uvel * np.ones((xdim, ydim), dtype=np.float32)
    V = vvel * np.ones((xdim, ydim), dtype=np.float32)
    return Grid.from_data(U, lon, lat, V, lon, lat, mesh='spherical')


def periodicBC(particle, grid, time, dt):
    particle.lon = math.fmod(particle.lon, 1)
    particle.lat = math.fmod(particle.lat, 1)


@pytest.mark.parametrize('mode', ['scipy', 'jit'])
def test_advection_periodic_zonal(mode, xdim=100, ydim=100, halosize=3):
    grid = periodicgrid(xdim, ydim, uvel=1., vvel=0.)
    grid.add_periodic_halo(zonal=True, halosize=halosize)
    assert(len(grid.U.lon) == xdim + 2 * halosize)

    pset = ParticleSet(grid, pclass=ptype[mode], lon=[0.5], lat=[0.5])
    pset.execute(AdvectionRK4 + pset.Kernel(periodicBC), endtime=delta(hours=20), dt=delta(seconds=30))
    assert abs(pset[0].lon - 0.15) < 0.1


@pytest.mark.parametrize('mode', ['scipy', 'jit'])
def test_advection_periodic_meridional(mode, xdim=100, ydim=100):
    grid = periodicgrid(xdim, ydim, uvel=0., vvel=1.)
    grid.add_periodic_halo(meridional=True)
    assert(len(grid.U.lat) == ydim + 10)  # default halo size is 5 grid points

    pset = ParticleSet(grid, pclass=ptype[mode], lon=[0.5], lat=[0.5])
    pset.execute(AdvectionRK4 + pset.Kernel(periodicBC), endtime=delta(hours=20), dt=delta(seconds=30))
    assert abs(pset[0].lat - 0.15) < 0.1


@pytest.mark.parametrize('mode', ['scipy', 'jit'])
def test_advection_periodic_zonal_meridional(mode, xdim=100, ydim=100):
    grid = periodicgrid(xdim, ydim, uvel=1., vvel=1.)
    grid.add_periodic_halo(zonal=True, meridional=True)
    assert(len(grid.U.lat) == ydim + 10)  # default halo size is 5 grid points
    assert(len(grid.U.lon) == xdim + 10)  # default halo size is 5 grid points
    assert np.allclose(np.diff(grid.U.lat), grid.U.lat[1]-grid.U.lat[0], rtol=0.001)
    assert np.allclose(np.diff(grid.U.lon), grid.U.lon[1]-grid.U.lon[0], rtol=0.001)

    pset = ParticleSet(grid, pclass=ptype[mode], lon=[0.4], lat=[0.5])
    pset.execute(AdvectionRK4 + pset.Kernel(periodicBC), endtime=delta(hours=20), dt=delta(seconds=30))
    assert abs(pset[0].lon - 0.05) < 0.1
    assert abs(pset[0].lat - 0.15) < 0.1


def truth_stationary(x_0, y_0, t):
    lat = y_0 - u_0 / f * (1 - math.cos(f * t))
    lon = x_0 + u_0 / f * math.sin(f * t)
    return lon, lat


@pytest.fixture
def grid_stationary(xdim=100, ydim=100, maxtime=delta(hours=6)):
    """Generate a grid encapsulating the flow field of a stationary eddy.

    Reference: N. Fabbroni, 2009, "Numerical simulations of passive
    tracers dispersion in the sea"
    """
    lon = np.linspace(0, 25000, xdim, dtype=np.float32)
    lat = np.linspace(0, 25000, ydim, dtype=np.float32)
    time = np.arange(0., maxtime.total_seconds(), 60., dtype=np.float64)
    U = np.ones((xdim, ydim, 1), dtype=np.float32) * u_0 * np.cos(f * time)
    V = np.ones((xdim, ydim, 1), dtype=np.float32) * -u_0 * np.sin(f * time)
    return Grid.from_data(np.asarray(U, np.float32), lon, lat,
                          np.asarray(V, np.float32), lon, lat,
                          time=time, mesh='flat')


@pytest.mark.parametrize('mode', ['scipy', 'jit'])
@pytest.mark.parametrize('method, rtol', [
    ('EE', 1e-2),
    ('RK4', 1e-5),
    ('RK45', 1e-5)])
def test_stationary_eddy(grid_stationary, mode, method, rtol, npart=1):
    grid = grid_stationary
    lon = np.linspace(12000, 21000, npart, dtype=np.float32)
    lat = np.linspace(12500, 12500, npart, dtype=np.float32)
    pset = ParticleSet(grid, pclass=ptype[mode], lon=lon, lat=lat)
    endtime = delta(hours=6).total_seconds()
    pset.execute(kernel[method], dt=delta(minutes=3), endtime=endtime)
    exp_lon = [truth_stationary(x, y, endtime)[0] for x, y, in zip(lon, lat)]
    exp_lat = [truth_stationary(x, y, endtime)[1] for x, y, in zip(lon, lat)]
    assert np.allclose(np.array([p.lon for p in pset]), exp_lon, rtol=rtol)
    assert np.allclose(np.array([p.lat for p in pset]), exp_lat, rtol=rtol)


def truth_moving(x_0, y_0, t):
    lat = y_0 - (u_0 - u_g) / f * (1 - math.cos(f * t))
    lon = x_0 + u_g * t + (u_0 - u_g) / f * math.sin(f * t)
    return lon, lat


@pytest.fixture
def grid_moving(xdim=100, ydim=100, maxtime=delta(hours=6)):
    """Generate a grid encapsulating the flow field of a moving eddy.

    Reference: N. Fabbroni, 2009, "Numerical simulations of passive
    tracers dispersion in the sea"
    """
    lon = np.linspace(0, 25000, xdim, dtype=np.float32)
    lat = np.linspace(0, 25000, ydim, dtype=np.float32)
    time = np.arange(0., maxtime.total_seconds(), 60., dtype=np.float64)
    U = np.ones((xdim, ydim, 1), dtype=np.float32) * u_g + (u_0 - u_g) * np.cos(f * time)
    V = np.ones((xdim, ydim, 1), dtype=np.float32) * -(u_0 - u_g) * np.sin(f * time)
    return Grid.from_data(np.asarray(U, np.float32), lon, lat,
                          np.asarray(V, np.float32), lon, lat,
                          time=time, mesh='flat')


@pytest.mark.parametrize('mode', ['scipy', 'jit'])
@pytest.mark.parametrize('method, rtol', [
    ('EE', 1e-2),
    ('RK4', 1e-5),
    ('RK45', 1e-5)])
def test_moving_eddy(grid_moving, mode, method, rtol, npart=1):
    grid = grid_moving
    lon = np.linspace(12000, 21000, npart, dtype=np.float32)
    lat = np.linspace(12500, 12500, npart, dtype=np.float32)
    pset = ParticleSet(grid, pclass=ptype[mode], lon=lon, lat=lat)
    endtime = delta(hours=6).total_seconds()
    pset.execute(kernel[method], dt=delta(minutes=3), endtime=endtime)
    exp_lon = [truth_moving(x, y, endtime)[0] for x, y, in zip(lon, lat)]
    exp_lat = [truth_moving(x, y, endtime)[1] for x, y, in zip(lon, lat)]
    assert np.allclose(np.array([p.lon for p in pset]), exp_lon, rtol=rtol)
    assert np.allclose(np.array([p.lat for p in pset]), exp_lat, rtol=rtol)


def truth_decaying(x_0, y_0, t):
    lat = y_0 - ((u_0 - u_g) * f / (f ** 2 + gamma ** 2) *
                 (1 - np.exp(-gamma * t) * (np.cos(f * t) + gamma / f * np.sin(f * t))))
    lon = x_0 + (u_g / gamma_g * (1 - np.exp(-gamma_g * t)) +
                 (u_0 - u_g) * f / (f ** 2 + gamma ** 2) *
                 (gamma / f + np.exp(-gamma * t) *
                  (math.sin(f * t) - gamma / f * math.cos(f * t))))
    return lon, lat


@pytest.fixture
def grid_decaying(xdim=100, ydim=100, maxtime=delta(hours=6)):
    """Generate a grid encapsulating the flow field of a decaying eddy.

    Reference: N. Fabbroni, 2009, "Numerical simulations of passive
    tracers dispersion in the sea"
    """
    lon = np.linspace(0, 25000, xdim, dtype=np.float32)
    lat = np.linspace(0, 25000, ydim, dtype=np.float32)
    time = np.arange(0., maxtime.total_seconds(), 60., dtype=np.float64)
    U = np.ones((xdim, ydim, 1), dtype=np.float32) * u_g *\
        np.exp(-gamma_g * time) + (u_0 - u_g) * np.exp(-gamma * time) * np.cos(f * time)
    V = np.ones((xdim, ydim, 1), dtype=np.float32) * -(u_0 - u_g) *\
        np.exp(-gamma * time) * np.sin(f * time)
    return Grid.from_data(np.asarray(U, np.float32), lon, lat,
                          np.asarray(V, np.float32), lon, lat,
                          time=time, mesh='flat')


@pytest.mark.parametrize('mode', ['scipy', 'jit'])
@pytest.mark.parametrize('method, rtol', [
    ('EE', 1e-2),
    ('RK4', 1e-5),
    ('RK45', 1e-5)])
def test_decaying_eddy(grid_decaying, mode, method, rtol, npart=1):
    grid = grid_decaying
    lon = np.linspace(12000, 21000, npart, dtype=np.float32)
    lat = np.linspace(12500, 12500, npart, dtype=np.float32)
    pset = ParticleSet(grid, pclass=ptype[mode], lon=lon, lat=lat)
    endtime = delta(hours=6).total_seconds()
    pset.execute(kernel[method], dt=delta(minutes=3), endtime=endtime)
    exp_lon = [truth_decaying(x, y, endtime)[0] for x, y, in zip(lon, lat)]
    exp_lat = [truth_decaying(x, y, endtime)[1] for x, y, in zip(lon, lat)]
    assert np.allclose(np.array([p.lon for p in pset]), exp_lon, rtol=rtol)
    assert np.allclose(np.array([p.lat for p in pset]), exp_lat, rtol=rtol)


if __name__ == "__main__":
    p = ArgumentParser(description="""
Example of particle advection around an idealised peninsula""")
    p.add_argument('mode', choices=('scipy', 'jit'), nargs='?', default='jit',
                   help='Execution mode for performing computation')
    p.add_argument('-p', '--particles', type=int, default=1,
                   help='Number of particles to advect')
    p.add_argument('-v', '--verbose', action='store_true', default=False,
                   help='Print particle information before and after execution')
    p.add_argument('--grid', choices=('stationary', 'moving', 'decaying'),
                   default='stationary', help='Generate grid file with given dimensions')
    p.add_argument('-m', '--method', choices=('RK4', 'EE', 'RK45'), default='RK4',
                   help='Numerical method used for advection')
    args = p.parse_args()
    filename = 'analytical_eddies'

    # Generate grid files according to chosen test setup
    if args.grid == 'stationary':
        grid = grid_stationary()
    elif args.grid == 'moving':
        grid = grid_moving()
    elif args.grid == 'decaying':
        grid = grid_decaying()

    npart = args.particles
    pset = ParticleSet(grid, pclass=ptype[args.mode],
                       lon=np.linspace(4000, 21000, npart, dtype=np.float32),
                       lat=np.linspace(12500, 12500, npart, dtype=np.float32))
    if args.verbose:
        print("Initial particle positions:\n%s" % pset)
    pset.execute(kernel[args.method], dt=delta(minutes=3), endtime=delta(hours=6))
    if args.verbose:
        print("Final particle positions:\n%s" % pset)
