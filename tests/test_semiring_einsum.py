import math
import unittest

import numpy
import torch

from semiring_einsum import (
    compile_equation,
    real_einsum_forward,
    real_einsum_backward,
    einsum,
    logspace_einsum_forward,
    logspace_einsum_backward,
    logspace_einsum,
    logspace_viterbi_einsum_forward)

EQUATION_STR = 'abce,abde,abdf->acd'
A, B, C, D, E, F = 2, 3, 5, 7, 11, 13
SIZES = [(A, B, C, E), (A, B, D, E), (A, B, D, F)]
OUTPUT_SIZE = (A, C, D)

class TestCompileEquation(unittest.TestCase):

    def test_compile_equation(self):
        compile_equation(EQUATION_STR, backward=False)
        compile_equation(EQUATION_STR)

class TestSemiringEinsum(unittest.TestCase):

    def setUp(self):
        self.device = torch.device('cpu')
        self.generator = torch.manual_seed(123)

    def test_real_einsum_forward(self):
        args = [
            torch.rand(size, device=self.device, generator=self.generator)
            for size in SIZES
        ]
        expected_result = torch.einsum(EQUATION_STR, *args)
        self.assertEqual(expected_result.size(), OUTPUT_SIZE)
        result = real_einsum_forward(
            compile_equation(EQUATION_STR, backward=False),
            *args)
        self.assertEqual(result.size(), OUTPUT_SIZE)
        numpy.testing.assert_allclose(result, expected_result, rtol=1e-6)

    def test_real_einsum_backward(self):
        args = [
            torch.nn.Parameter(torch.rand(
                size, device=self.device, generator=self.generator))
            for size in SIZES
        ]
        grad = torch.empty(OUTPUT_SIZE, device=self.device)
        grad.uniform_(-5.0, 5.0, generator=self.generator)
        expected_output = torch.einsum(EQUATION_STR, *args)
        expected_output.backward(grad)
        expected_grads = [arg.grad.clone() for arg in args]
        arg_grads = real_einsum_backward(
            compile_equation(EQUATION_STR, forward=False),
            [arg.detach() for arg in args],
            [True for arg in args],
            grad)
        for arg_grad, arg_size in zip(arg_grads, SIZES):
            self.assertEqual(arg_grad.size(), arg_size)
        for arg_grad, expected_grad in zip(arg_grads, expected_grads):
            numpy.testing.assert_allclose(arg_grad, expected_grad, rtol=1e-5)

    def test_einsum(self):
        args = [
            torch.nn.Parameter(torch.rand(
                size, device=self.device, generator=self.generator))
            for size in SIZES
        ]
        expected_output = torch.einsum(EQUATION_STR, *args)
        expected_loss = expected_output.sum()
        expected_loss.backward()
        expected_grads = [arg.grad.clone() for arg in args]
        for arg in args:
            arg.grad.zero_()
        output = einsum(
            compile_equation(EQUATION_STR),
            *args)
        loss = output.sum()
        loss.backward()
        grads = [arg.grad.clone() for arg in args]
        for grad, expected_grad in zip(grads, expected_grads):
            numpy.testing.assert_allclose(grad, expected_grad, rtol=1e-6)

    def test_logspace_einsum_forward(self):
        args = [
            torch.empty(size, device=self.device)
            for size in SIZES
        ]
        for arg in args:
            arg.uniform_(-10.0, 10.0, generator=self.generator)
        exp_args = [torch.exp(arg) for arg in args]
        exp_result = torch.einsum(EQUATION_STR, *exp_args)
        expected_result = torch.log(exp_result)
        self.assertEqual(expected_result.size(), OUTPUT_SIZE)
        result = logspace_einsum_forward(
            compile_equation(EQUATION_STR, backward=False),
            *args)
        self.assertEqual(result.size(), OUTPUT_SIZE)
        numpy.testing.assert_allclose(result, expected_result)

    def test_logspace_einsum_backward(self):
        args = [
            torch.nn.Parameter(torch.empty(size, device=self.device))
            for size in SIZES
        ]
        for arg in args:
            arg.data.uniform_(-10.0, 10.0, generator=self.generator)
        grad = torch.empty(OUTPUT_SIZE, device=self.device)
        grad.uniform_(-5.0, 5.0, generator=self.generator)
        exp_args = [torch.exp(arg) for arg in args]
        exp_result = torch.einsum(EQUATION_STR, *exp_args)
        expected_output = torch.log(exp_result)
        expected_output.backward(grad)
        expected_grads = [arg.grad.clone() for arg in args]
        arg_grads = logspace_einsum_backward(
            compile_equation(EQUATION_STR, forward=False),
            [arg.detach() for arg in args],
            [True for arg in args],
            grad)
        for arg_grad, arg_size in zip(arg_grads, SIZES):
            self.assertEqual(arg_grad.size(), arg_size)
        for arg_grad, expected_grad in zip(arg_grads, expected_grads):
            numpy.testing.assert_allclose(arg_grad, expected_grad, rtol=1e-3)

    def test_logspace_einsum(self):
        args = [
            torch.nn.Parameter(torch.rand(
                size, device=self.device, generator=self.generator))
            for size in SIZES
        ]
        expected_output = torch.einsum(EQUATION_STR, *args)
        expected_loss = expected_output.sum()
        expected_loss.backward()
        expected_grads = [arg.grad.clone() for arg in args]
        for arg in args:
            arg.grad.zero_()
        log_output = logspace_einsum(
            compile_equation(EQUATION_STR),
            *[torch.log(arg) for arg in args])
        output = torch.exp(log_output)
        loss = output.sum()
        loss.backward()
        grads = [arg.grad.clone() for arg in args]
        for grad, expected_grad in zip(grads, expected_grads):
            numpy.testing.assert_allclose(grad, expected_grad, rtol=1e-6)

    def test_logspace_viterbi_einsum_forward(self):
        args = [
            torch.empty(size, device=self.device)
            for size in SIZES
        ]
        for arg in args:
            arg.uniform_(-10.0, 10.0, generator=self.generator)
        expected_maxval, expected_argmax = reference_logspace_viterbi_einsum(
            *args, self.device)
        self.assertEqual(expected_maxval.size(), OUTPUT_SIZE)
        self.assertEqual(expected_argmax.size(), (*OUTPUT_SIZE, 3))
        maxval, argmax = logspace_viterbi_einsum_forward(
            compile_equation(EQUATION_STR, backward=False),
            *args)
        self.assertEqual(expected_maxval.size(), OUTPUT_SIZE)
        self.assertEqual(expected_argmax.size(), (*OUTPUT_SIZE, 3))
        numpy.testing.assert_allclose(maxval, expected_maxval)
        self.assertTrue(torch.equal(argmax, expected_argmax))

def reference_logspace_viterbi_einsum(X1, X2, X3, device):
    Y_max = []
    Y_argmax = []
    for a in range(A):
        Y_max_a = []
        Y_argmax_a = []
        for c in range(C):
            Y_max_ac = []
            Y_argmax_ac = []
            for d in range(D):
                maxval = torch.tensor(-math.inf, device=device)
                argmax = None
                for b in range(B):
                    for e in range(E):
                        for f in range(F):
                            val = (
                                X1[a, b, c, e]
                                + X2[a, b, d, e]
                                + X3[a, b, d, f]
                            )
                            if val > maxval:
                                maxval = val
                                argmax = torch.tensor([b, e, f], device=device)
                Y_max_ac.append(maxval)
                Y_argmax_ac.append(argmax)
            Y_max_a.append(Y_max_ac)
            Y_argmax_a.append(Y_argmax_ac)
        Y_max.append(Y_max_a)
        Y_argmax.append(Y_argmax_a)
    return recursively_stack(Y_max), recursively_stack(Y_argmax)

def recursively_stack(tensors):
    if isinstance(tensors, torch.Tensor):
        return tensors
    else:
        return torch.stack([recursively_stack(x) for x in tensors])

if __name__ == '__main__':
    unittest.main()