from scipy.interpolate import RectBivariateSpline
from cachetools import cachedmethod, LRUCache
from collections import Iterable
from py import path
import numpy as np
from xray import DataArray, Dataset
import operator
import matplotlib.pyplot as plt
from ctypes import Structure, c_int, c_float, c_double, POINTER
from netCDF4 import num2date


__all__ = ['CentralDifferences', 'Field']


def CentralDifferences(field_data, lat, lon):
    r = 6.371e6  # radius of the earth
    deg2rd = np.pi / 180
    dy = r * np.diff(lat) * deg2rd
    # calculate the width of each cell, dependent on lon spacing and latitude
    dx = np.zeros([len(lon)-1, len(lat)], dtype=np.float32)
    for x in range(len(lon))[1:]:
        for y in range(len(lat)):
            dx[x-1, y] = r * np.cos(lat[y] * deg2rd) * (lon[x]-lon[x-1]) * deg2rd
    # calculate central differences for non-edge cells (with equal weighting)
    dVdx = np.zeros(shape=np.shape(field_data), dtype=np.float32)
    dVdy = np.zeros(shape=np.shape(field_data), dtype=np.float32)
    for x in range(len(lon))[1:-1]:
        for y in range(len(lat)):
            dVdx[x, y] = (field_data[x+1, y] - field_data[x-1, y]) / (2 * dx[x-1, y])
    for x in range(len(lon)):
        for y in range(len(lat))[1:-1]:
            dVdy[x, y] = (field_data[x, y+1] - field_data[x, y-1]) / (2 * dy[y-1])
    # Forward and backward difference for edges
    for x in range(len(lon)):
        dVdy[x, 0] = (field_data[x, 1] - field_data[x, 0]) / dy[0]
        dVdy[x, len(lat)-1] = (field_data[x, len(lat)-1] - field_data[x, len(lat)-2]) / dy[len(lat)-2]
    for y in range(len(lat)):
        dVdx[0, y] = (field_data[1, y] - field_data[0, y]) / dx[0, y]
        dVdx[len(lon)-1, y] = (field_data[len(lon)-1, y] - field_data[len(lon)-2, y]) / dx[len(lon)-2, y]

    return [dVdx, dVdy]


class Field(object):
    """Class that encapsulates access to field data.

    :param name: Name of the field
    :param data: 2D array of field data
    :param lon: Longitude coordinates of the field
    :param lat: Latitude coordinates of the field
    :param transpose: Transpose data to required (lon, lat) layout
    """

    def __init__(self, name, data, lon, lat, depth, time=None,
                 transpose=False, vmin=None, vmax=None, time_origin=0):
        self.name = name
        self.data = data
        self.lon = lon
        self.lat = lat
        self.depth = depth
        self.time = np.zeros(1, dtype=np.float64) if time is None else time
        self.time_origin = time_origin

        # Ensure that field data is the right data type
        if not self.data.dtype == np.float32:
            print("WARNING: Casting field data to np.float32")
            self.data = self.data.astype(np.float32)
        if transpose:
            # Make a copy of the transposed array to enforce
            # C-contiguous memory layout for JIT mode.
            self.data = np.transpose(self.data).copy()
        if self.depth.size > 1:
            self.data = self.data.reshape((self.time.size, self.depth.size,
                                           self.lat.size, self.lon.size))
        else:
            self.data = self.data.reshape((self.time.size, self.lat.size, self.lon.size))

        # Hack around the fact that NaN and ridiculously large values
        # propagate in SciPy's interpolators
        if vmin is not None:
            self.data[self.data < vmin] = 0.
        if vmax is not None:
            self.data[self.data > vmax] = 0.
        self.data[np.isnan(self.data)] = 0.

        # Variable names in JIT code
        self.ccode_data = self.name
        self.ccode_lon = self.name + "_lon"
        self.ccode_lat = self.name + "_lat"

        self.interpolator_cache = LRUCache(maxsize=2)
        self.find_higher_index_cache = LRUCache(maxsize=2)

    @classmethod
    def from_netcdf(cls, name, dimensions, datasets, **kwargs):
        """Create field from netCDF file using NEMO conventions

        :param name: Name of the field to create
        :param dimensions: Variable names for the relevant dimensions
        :param dataset: Single or multiple netcdf.Dataset object(s)
        containing field data. If multiple datasets are present they
        will be concatenated along the time axis
        """
        if not isinstance(datasets, Iterable):
            datasets = [datasets]
        lon = datasets[0][dimensions['lon']]
        lon = lon[0, :] if len(lon.shape) > 1 else lon[:]
        lat = datasets[0][dimensions['lat']]
        lat = lat[:, 0] if len(lat.shape) > 1 else lat[:]
        # Default depth to zeros until we implement 3D grids properly
        depth = datasets[0][dimensions['depth']][:]
        # Concatenate time variable to determine overall dimension
        # across multiple files
        timeslices = [dset[dimensions['time']][:] for dset in datasets]
        time = np.concatenate(timeslices)

        # assign time_origin if the time dimension has units and calendar
        try:
            time_units = datasets[0][dimensions['time']].units
            calendar = datasets[0][dimensions['time']].calendar
            time_origin = num2date(0, time_units, calendar)
        except:
            time_origin = 0

        # Pre-allocate grid data before reading files into buffer
        data = np.empty((time.size, depth.size, lat.size, lon.size), dtype=np.float32)
        tidx = 0
        for tslice, dset in zip(timeslices, datasets):
            data[tidx:, :, :, :] = dset[dimensions['data']][:, :, :, :]
            tidx += tslice.size
        return cls(name, data, lon, lat, depth=depth, time=time,
                   time_origin=time_origin, **kwargs)

    def __getitem__(self, key):
        return self.eval(*key)

    def gradient(self, timerange=None, lonrange=None, latrange=None, name=None):
        if name is None:
            name = 'd' + self.name

        if timerange is None:
            time_i = range(len(self.time))
            time = self.time
        else:
            time_i = range(np.where(self.time >= timerange[0])[0][0], np.where(self.time <= timerange[1])[0][-1]+1)
            time = self.time[time_i]
        if lonrange is None:
            lon_i = range(len(self.lon))
            lon = self.lon
        else:
            lon_i = range(np.where(self.lon >= lonrange[0])[0][0], np.where(self.lon <= lonrange[1])[0][-1]+1)
            lon = self.lon[lon_i]
        if latrange is None:
            lat_i = range(len(self.lat))
            lat = self.lat
        else:
            lat_i = range(np.where(self.lat >= latrange[0])[0][0], np.where(self.lat <= latrange[1])[0][-1]+1)
            lat = self.lat[lat_i]

        dVdx = np.zeros(shape=(time.size, lat.size, lon.size), dtype=np.float32)
        dVdy = np.zeros(shape=(time.size, lat.size, lon.size), dtype=np.float32)
        for t in np.nditer(np.int32(time_i)):
            grad = CentralDifferences(np.transpose(self.data[t, :, :][np.ix_(lat_i, lon_i)]), lat, lon)
            dVdx[t, :, :] = np.array(np.transpose(grad[0]))
            dVdy[t, :, :] = np.array(np.transpose(grad[1]))

        return([Field(name + '_dx', dVdx, lon, lat, self.depth, time),
                Field(name + '_dy', dVdy, lon, lat, self.depth, time)])

    def interpolator3D(self, idx, time, z, y, x):
        # First interpolate in the horizontal, then in the vertical
        zdx = self.find_higher_index('depth', z)
        f0 = self.interpolator2D(idx, z_idx=zdx-1).ev(y, x)
        f1 = self.interpolator2D(idx, z_idx=zdx).ev(y, x)
        z0 = self.depth[zdx-1]
        z1 = self.depth[zdx]
        return f0 + (f1 - f0) * ((z - z0) / (z1 - z0))

    @cachedmethod(operator.attrgetter('interpolator_cache'))
    def interpolator2D(self, t_idx, z_idx=None):
        if z_idx is None:
            return RectBivariateSpline(self.lat, self.lon,
                                       self.data[t_idx, :])
        else:
            return RectBivariateSpline(self.lat, self.lon,
                                       self.data[t_idx, z_idx, :, :])

    def interpolator1D(self, idx, time, y, x):
        # Return linearly interpolated field value:
        if x is None and y is None:
            t0 = self.time[idx-1]
            t1 = self.time[idx]
            f0 = self.data[idx-1, :]
            f1 = self.data[idx, :]
        else:
            f0 = self.interpolator2D(idx-1).ev(y, x)
            f1 = self.interpolator2D(idx).ev(y, x)
            t0 = self.time[idx-1]
            t1 = self.time[idx]
        return f0 + (f1 - f0) * ((time - t0) / (t1 - t0))

    @cachedmethod(operator.attrgetter('find_higher_index_cache'))
    def find_higher_index(self, field, var):
        field = getattr(self, field)
        index = field < var
        if index.all():
            # If given var > last known grid index, use
            # the last grid frame without interpolation
            return -1
        else:
            return index.argmin()

    def eval(self, time, x, y, z):
        idx = self.find_higher_index('time', time)
        if idx > 0:
            return self.interpolator1D(idx, time, y, x)
        elif self.depth.size == 1:
            return self.interpolator2D(idx).ev(y, x)
        else:
            return self.interpolator3D(idx, time, z, y, x)

    def ccode_subscript(self, t, x, y, z):
        ccode = "temporal_interpolation_linear(%s, %s, %s, %s, %s, %s, %s, %s)" \
                % (z, y, x, "particle->zi", "particle->yi", "particle->xi", t, self.name)
        return ccode

    @property
    def ctypes_struct(self):
        """Returns a ctypes struct object containing all relevnt
        pointers and sizes for this field."""

        # Ctypes struct corresponding to the type definition in parcels.h
        class CField(Structure):
            _fields_ = [('xdim', c_int), ('ydim', c_int),
                        ('tdim', c_int), ('tidx', c_int),
                        ('lon', POINTER(c_float)), ('lat', POINTER(c_float)),
                        ('time', POINTER(c_double)),
                        ('data', POINTER(POINTER(c_float)))]

        # Create and populate the c-struct object
        cstruct = CField(self.lat.size, self.lon.size, self.time.size, 0,
                         self.lat.ctypes.data_as(POINTER(c_float)),
                         self.lon.ctypes.data_as(POINTER(c_float)),
                         self.time.ctypes.data_as(POINTER(c_double)),
                         self.data.ctypes.data_as(POINTER(POINTER(c_float))))
        return cstruct

    def show(self, **kwargs):
        t = kwargs.get('t', 0)
        animation = kwargs.get('animation', False)
        idx = self.find_higher_index('time', t)
        if self.time.size > 1:
            data = np.squeeze(self.interpolator1D(idx, t, None, None))
        elif self.data.ndim == 3:
            data = np.squeeze(self.data[0, :, :])
        elif self.data.ndim == 4:
            data = np.squeeze(self.data[0, 0, :, :])
        else:
            data = self.data
        vmin = kwargs.get('vmin', data.min())
        vmax = kwargs.get('vmax', data.max())
        cs = plt.contourf(self.lon, self.lat, data,
                          levels=np.linspace(vmin, vmax, 256))
        cs.cmap.set_over('k')
        cs.cmap.set_under('w')
        cs.set_clim(vmin, vmax)
        plt.colorbar(cs)
        if not animation:
            plt.show()

    def write(self, filename, varname=None):
        filepath = str(path.local('%s%s.nc' % (filename, self.name)))
        if varname is None:
            varname = self.name
        # Derive name of 'depth' variable for NEMO convention
        vname_depth = 'depth'

        # Create DataArray objects for file I/O
        t, d, x, y = (self.time.size, self.depth.size,
                      self.lon.size, self.lat.size)
        nav_lon = DataArray(self.lon + np.zeros((y, x), dtype=np.float32),
                            coords=[('y', self.lat), ('x', self.lon)])
        nav_lat = DataArray(self.lat.reshape(y, 1) + np.zeros(x, dtype=np.float32),
                            coords=[('y', self.lat), ('x', self.lon)])
        vardata = DataArray(self.data.reshape((t, d, y, x)),
                            coords=[('time_counter', self.time),
                                    (vname_depth, self.depth),
                                    ('y', self.lat), ('x', self.lon)])
        # Create xray Dataset and output to netCDF format
        dset = Dataset({varname: vardata}, coords={'nav_lon': nav_lon,
                                                   'nav_lat': nav_lat})
        dset.to_netcdf(filepath)
