r""".. _spsa:

Optimization using SPSA
=======================

.. meta::
    :property="og:description": Use the simultaneous perturbation stochastic
        approximation algorithm to optimize variational circuits in PennyLane.
    :property="og:image": https://pennylane.ai/qml/_images/pes_h2.png

.. related::

   tutorial_vqe A brief overview of VQE
   tutorial_vqe_qng Accelerating VQE with the QNG


Background
----------

PennyLane allows computing quantum gradients using  parameter-shift rules.

For quantum circuits that have multiple free parameters, using the
parameter-shift rule to compute quantum gradients involves computing the
partial derivatives of the quantum function w.r.t. each free parameter. These
partial derivatives are then used to apply the product rule when computing the
quantum gradient (`see parameter-shift rules
<https://pennylane.ai/qml/glossary/parameter_shift.html>`_). For qubit
operations that are generated by one of the Pauli matrices, each partial
derivative computation will involve two quantum circuit evaluations with a
positive and a negative shift in the parameter values.

As in such cases there would be two circuit evaluation for each free parameter,
the number of overall quantum circuit executions for computing a quantum
gradient scales linearly with the number of free parameters: :math:`O(k)` with
:math:`k` being the number of free parameters. This scaling can be very costly
for optimization tasks where many free pramaeters are considered in the quantum
circuit. For the overall optimization this scaling gives :math:`O(k*n)` quantum
circuit evaluations with :math:`n` being the number of optimization steps taken.

There are, however, certain optimization techniques that are gradient-free and
hence offer othen approach analytically computing the gradients of quantum
circuits.

One of such techniques is called Simultaneous perturbation stochastic
approximation (SPSA), an optimization method that involves approximating the
gradient of the cost function at each iteration step. This technique involves
only two quantum circuit executions per iteration step, regardless of the
number of free parameters. Therefore the overall number of circuit executions
would be :math:`O(n')` where :math:`n'` is the number of optimization steps taken when
using SPSA. This technique was also found to be robust against noise, making it
a great optimization method in the NISQ era.

Let's have a look at the details of how exactly this technique works.

Simultaneous perturbation stochastic approximation (SPSA)
---------------------------------------------------------

SPSA is a general method for minimizing differentiable multivariate functions
mostly tailored towards those functions for which evaluating the gradient is
not available.

SPSA provides a stochastic method for approximating the gradient of a
multivariate differentiable cost function without having to evaluate the
gradient of the function. To approximate the gradient, the cost function is
evaluated twice using perturbed parameter vectors: every component of the
original parameter vector is simultaneously shifted with a randomly generated
value. This is in contrast to finite-differences methods where for each
evaluation only one component of the parameter vector is shifted.

Similar to gradient-based approaches such as gradient descent, SPSA offers an
iterative optimization algorithm. We consider a differentiable cost function
:math:`L(\theta)` where :math:`\theta` is a :math:`p-dimensional` vector and where the
optimization problem can be translated into  finding a :math:`\theta*` such that
:math:`\frac{\partial L}{\partial u} = 0`.  It is assumed that measurements of
:math:`L(\theta)` are available at various values of :math:`\theta`.

This is exactly the problem that we'd consider when optimizing quantum
functions!

.. figure:: ../demonstrations/spsa/spsa_opt.png
    :align: center
    :width: 60%

    ..

    A schematic of the search paths used by gradient descent with
    parameter-shift and SPSA in a low-noise setting.
    Image source: [#spall_overview]_.

Just like with gradient-based methods, we'd start with a :math:`\hat{\theta}_{0}`
initial parameter vector. After :math:`k` iterations, the :math:`k+1.` parameter iterates
can be obtained as

.. math:: \hat{\theta}_{k+1} = \hat{\theta}_{k} - a_{k}\hat{g}_{k}(\hat{\theta}_{k})

where :math:`\hat{g}_{k}` is the estimate of the gradient :math:`g(u) = \frac{
\partial L}{\partial \theta}` at the iterate :math:`\hat{\theta}_{k}` based on
prior measurements of the cost function and :math:`a_{k}` is a positive number.

As previously mentioned, SPSA further takes into account the noisiness of the
result obtained when measuring function :math:`L`. Therefore, let's consider the
function :math:`y(\theta)=L(\theta) + noise`.

Using :math:`y`, the estimated gradient at each iteration step is expressed as

.. math:: \hat{g}_{ki} (\hat{\theta}_{k}) = \frac{y(\hat{\theta}_{k} +c_{k}\Delta_{k})
    - y(\hat{\theta}_{k} -c_{k}\Delta_{k})}{2c_{k}\Delta_{ki}}

where :math:`c_{k}` is a positive number and :math:`\Delta_{k} = (\Delta_{k_1},
\Delta_{k_2}, ..., \Delta_{k_p})^{T}` is the perturbation vector. The
stochasticity of the technique comes from the fact that for each iteration step
:math:`k` the components of the :math:`\Delta_{k}` perturbation vector are randomly
generated using a zero-mean distribution. In most cases, the Bernoulli
distribution is used.

Now that we have explored how SPSA works, let's see how it performs in an
optimization!

Optimization on a sampling device
---------------------------------

.. important::

    In order to run this demo locally, you'll need to install the `noisyopt
    <https://github.com/andim/noisyopt>`_ library. This library contains a
    straightforward implementation of SPSA that can be used in the same way as
    the optimizers available in `SciPy's minimize method
    <https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.minimize.html>`_.

First, let's consider a simple quantum circuit on a sampling device. For this,
we'll be using a device from the `PennyLane-Qiskit plugin
<https://pennylaneqiskit.readthedocs.io/en/latest/>`_ that samples quantum
circuits to get measurement outcomes and later post-processes these outcomes to
compute statistics like expectation values.

.. note::

    Just with other PennyLane devices, the number of samples taken for a device
    execution can be specified using the ``shots`` keyword argument of the
    device.

Once we have a device selected, we just need a couple of other ingredients to
put together the pieces for an example optimization:

* a template ``StronglyEntanglingLayers``,
* an observable: :math:`\bigotimes_{i=0}^{N-1}\sigma_z^i`, where :math:`N` stands
  for the number of qubits,
* initial parameters: conveniently generated using ``qml.init.strong_ent_layers_normal``.

"""
import pennylane as qml
import numpy as np

num_wires = 4
num_layers = 3

dev_sampler = qml.device(
    "qiskit.aer", wires=num_wires, shots=1000
)

##############################################################################
# We seed so that we can simulate the same circuit every time.
np.random.seed(50)

all_pauliz_tensor_prod = qml.operation.Tensor(*[qml.PauliZ(i) for i in range(num_wires)])

@qml.qnode(dev_sampler)
def circuit(params):
    qml.templates.StronglyEntanglingLayers(params, wires=list(range(num_wires)))
    return qml.expval(all_pauliz_tensor_prod)

##############################################################################
# After this, we'll initialize the parameters in a tricky way. We are
# flattening our parameters, which will be very convenient later on when using
# the SPSA optimizer. Just keep in mind that this is done for compatibility.
flat_shape = num_layers * num_wires * 3
init_params = qml.init.strong_ent_layers_normal(n_wires=num_wires, n_layers=num_layers).reshape(flat_shape)

def cost(params):
    return circuit(params.reshape(num_layers, num_wires, 3))


##############################################################################
# Once we have defined each piece of the optimization, there's only one
# remaining component required for the optimization: the *SPSA optimizer*.
#
# We'll use the SPSA optimizer provided by the ``noisyopt`` package. Once
# imported, we can initialize parts of the optimization such as the number of
# iterations, a collection to store the cost values and a callback function.
#
# This callback function is used to record the value of the cost function at
# each iteration step (and for our convenience to print values every 10 steps).
from noisyopt import minimizeSPSA

niter_spsa = 200

cost_store_spsa = []
device_execs_spsa = []

def callback_fn(xk):
    cost_val = cost(xk)
    cost_store_spsa.append(cost_val)
    device_execs_spsa.append(dev_sampler.num_executions)
    if len(cost_store_spsa) % 10 == 0:
        print(cost_val)

##############################################################################
# Choosing the hyperparameters
# ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#
# ``noisyopt`` allows specifying the initial value of two hyperparameters for
# SPSA: the :math:`c` and :math:`a` coefficients.
#
# With stochastic approximation, specifying such hyperparameters significantly
# influences the convergence of the optimization for a given problem. Although
# there is no universal recipe for selecting these values (as they are greatly
# dependent on the specific problem), [#spall_implementation]_ includes
# guidelines for the selection.
#
# In our case, the initial values for :math:`c` and :math:`a` were selected as
# a result of a grid search to ensure a fast convergence.
#
# Our cost function does not take a seed as a keyword argument (which would be
# the default behaviour for ``minimizeSPSA``), so we set ``paired=False``.
#
res = minimizeSPSA(cost, x0=init_params, niter=niter_spsa, paired=False, c=0.6, a=1.8, callback=callback_fn)

##############################################################################
# .. rst-class:: sphx-glr-script-out
#
#  Out:
#
#  .. code-block:: none
#
#     -0.496
#     -0.676
#     -0.864
#     -0.922
#     -0.924
#     -0.978
#     -0.974
#     -0.992
#     -0.982
#     -0.98
#     -0.992
#     -0.984
#     -0.996
#     -0.998
#     -0.992
#     -0.99
#     -0.992
#     -1.0
#     -0.99
#     -0.994

##############################################################################
#
# Once the optimization has concluded, we save the number of device executions
# required for completion (will be an interesting quantity later!).
device_execs_spsa = dev_sampler.num_executions

##############################################################################
#
# At this point, we perform the same optimization using gradient descent. We
# set the step size according to a favourable value found after grid search for
# fast convergence.
#
# Note that we also reset the number of executions of the device
opt = qml.GradientDescentOptimizer(stepsize=1.1)

dev_sampler._num_executions = 0

device_execs_grad = []
cost_store_grad = []

steps = 20
params = init_params

for k in range(steps):
    params, val = opt.step_and_cost(cost, params)
    device_execs_grad.append(dev_sampler.num_executions)
    cost_store_grad.append(val)
    print(val)

##############################################################################
# .. rst-class:: sphx-glr-script-out
#
#  Out:
#
#  .. code-block:: none
#
#     0.976
#     0.918
#     0.66
#     0.166
#     -0.542
#     -0.946
#     -0.998
#     -0.99
#     -1.0
#     -0.996
#     -1.0
#     -1.0
#     -0.998
#     -1.0
#     -1.0
#     -0.998
#     -1.0
#     -0.998
#     -0.996
#     -0.998

##############################################################################
# References
# ----------
#
# .. [#spall_overview]
#
#    1. James C. Spall, "An Overview of the Simultaneous Perturbation Method
#    for Efficient Optimization."
#    `<https://www.jhuapl.edu/SPSA/PDF-SPSA/Spall_An_Overview.PDF>`__, 1998
#
# .. [#spall_implementation]
#
#    2. J. C. Spall, "Implementation of the simultaneous perturbation algorithm
#    for stochastic optimization," in IEEE Transactions on Aerospace and
#    Electronic Systems, vol. 34, no. 3, pp. 817-823, July 1998, doi:
#    10.1109/7.705889.