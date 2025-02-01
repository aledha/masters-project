import numpy as np
import matplotlib.pyplot as plt
from dolfinx import io, fem
from mpi4py import MPI
import ufl
import sys
sys.path.append('../')

from src.hyperelasticity import HyperelasticProblem

def solve(h, lagrange_order=2, save_solution=False):
    problem = HyperelasticProblem(h, lagrange_order)
    problem.set_rectangular_domain(1, 1, 1, 0, 1)

    def left(x):
        return np.isclose(x[0], 0)
    def right(x):
        return np.isclose(x[0], 1)

    problem.boundary_conditions([left, right], vals=[0.0, 0], bc_types=['d1', 'n'])
    problem.holzapfel_ogden_model()
    problem.incompressible()
    def tension(x):
        return 5 * np.exp(-5*((x[1]-0.5)**2 + (x[2]-0.5)**2))
    problem.set_tension(tension)
    problem.setup_solver()

    if save_solution:
        vtx = io.VTXWriter(MPI.COMM_WORLD, "convergence.bp", [problem.u], engine="BP4")
        vtx.write(0.0)
    problem.solve()
    if save_solution:
        vtx.write(0.1)
        vtx.close()
    return problem.u

def L2_error_with_exact(h, u_fine, compute_in_coarse_space = True, lagrange_order = 2):
    # Approximating the coarser solution into finer function space and computing error there?
    # Should it be opposite?
    u_coarse = solve(h, lagrange_order)
    if compute_in_coarse_space:
        u_fine_interp = fem.Function(u_coarse.function_space)
        u_fine_interp.interpolate(u_fine,
                    nmm_interpolation_data=fem.create_nonmatching_meshes_interpolation_data(
                                        u_coarse.function_space.mesh, 
                                        u_coarse.function_space.element, 
                                        u_fine.function_space.mesh))
        comm = u_coarse.function_space.mesh.comm
        error = fem.form((u_fine_interp - u_coarse)**2 * ufl.dx) 
    else:
        u_coarse_interp = fem.Function(u_fine.function_space)
        u_coarse_interp.interpolate(u_coarse,
                    nmm_interpolation_data=fem.create_nonmatching_meshes_interpolation_data(
                                        u_fine.function_space.mesh, 
                                        u_fine.function_space.element, 
                                        u_coarse.function_space.mesh))
        comm = u_fine.function_space.mesh.comm
        error = fem.form((u_fine - u_coarse_interp)**2 * ufl.dx) 
    E = np.sqrt(comm.allreduce(fem.assemble_scalar(error), MPI.SUM))
    return E

def convergence_plot(h_exact, hs, plot_title, compute_in_coarse_space=True, lagrange_order = 2):
    u_fine = solve(h_exact)
    errors = np.zeros_like(hs)
    for i in range(len(hs)):
        errors[i] = L2_error_with_exact(hs[i], 
                                        u_fine, 
                                        compute_in_coarse_space=compute_in_coarse_space,
                                        lagrange_order = lagrange_order)

    order = (np.log(errors[-1]) - np.log(errors[-2])) / (np.log(hs[-1]) - np.log(hs[-2]))
    
    fig, ax = plt.subplots(figsize=(8,5))
    ax.loglog(hs, errors, '-o', label = "order = {:.3f}".format(order))
    ax.set_xlabel(r'$h$')
    ax.set_ylabel('Error')
    ax.set_title(f'Convergence plot of hyperelastic problem')
    ax.legend()
    fig.savefig(plot_title, bbox_inches='tight')
    fig.show()

h_exact = 0.075
hs = [0.1, 0.15, 0.2, 0.3, 0.4]
convergence_plot(h_exact, hs, "coarsespace.png", compute_in_coarse_space=True)
convergence_plot(h_exact, hs, "finespace.png", compute_in_coarse_space=False)