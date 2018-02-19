# -*- coding: utf-8 -*-
"""
@author: Fei Yan
"""

import numpy as np
from scipy.linalg import eig
from qutip import *
from basicfunc import *

import logging
log = logging.getLogger('LabberDriver')



def U(H,t):
	# unitary propagator generated by H over time t 
	H = Qobj(H)
	return Qobj(-1j * H * t).expm()

def T(A, U):
	A = Qobj(A)
	U = Qobj(U)
	return U * A * U.dag()

def Qflatten(Q):
	return Qobj(Q.full())

List_sPauli = ['I','X','Y','Z']
List_mPauli = [qeye(2), sigmax(), sigmay(), sigmaz()]
List_sQubit = ['Q1', 'Q2', 'Q3']
List_sSeqType = ['Frequency', 'Anharmonicity', 'DriveP']
List_sQubitParam = ['Frequency', 'Anharmonicity', 'Type', 'Ej', 'Ec', 'Asymmetry', 'Flux']
List_sCapParam = ['C1', 'C2', 'C3', 'C12', 'C23', 'C13']

dict_psi = {'+X': Qobj(np.array([1,1])).unit(),
			'-X': Qobj(np.array([1,-1])).unit(),
			'+Y': Qobj(np.array([1,1j])).unit(),
			'-Y': Qobj(np.array([1,-1j])).unit(),
			'+Z': Qobj(np.array([1,0])).unit(),
			'-Z': Qobj(np.array([0,1])).unit()}

# dict_sigma = {'+X': sigmax(),
# 			'-X': -sigmax(),
# 			'+Y': sigmay(),
# 			'-Y': -sigmay(),
# 			'+Z': sigmaz(),
# 			'-Z': -sigmaz()}

# dict_rho = {key: psi * psi.dag() for key, psi in dict_psi.items()}

dict_pauli16 = {}
for k1 in range(4):
	for k2 in range(4):
		key = List_sPauli[k1] + List_sPauli[k2]
		dict_pauli16[key] = Qflatten(tensor(List_mPauli[k1], List_mPauli[k2]))



def eigensolve(H):
	# find eigensolution of H
	H = H.full()
	vals, vecs = eig(H)    
	#idx = vals.argsort()[::-1] #Descending Order
	idx = vals.argsort() #Ascending Order
	vals = vals[idx]
	vecs = vecs[:,idx]
	return np.real(vals), vecs

def level_identify(vals, vecs, list_table, list_select):
	# identify and sort eigen solutions according to 'list_select'
	v_idx = []
	for k, str_level in enumerate(list_select):
		idx_sort = np.argsort(np.abs(vecs[list_table.index(str_level),:]))
		count = 1
		while True:
			if idx_sort[-count] in v_idx:
				count += 1
			else:
				v_idx.append(idx_sort[-count])
				break			
	return vals[v_idx], vecs[:,v_idx]

def generateBasicOperator(nTrunc):
	# generate basic operators. matrix truncated at nTrunc 
	I = qeye(nTrunc)
	a = destroy(nTrunc)
	x = a + a.dag()
	p = -1j*(a - a.dag())
	aa = a.dag() * a
	aaaa = a.dag() * a.dag() * a * a
	return {'I':I, 'a':a, 'x':x, 'p':p, 'aa':aa, 'aaaa':aaaa}


class QubitConfiguration():

	def __init__(self, sQubit, CONFIG):
		self.sQubit = sQubit
		self.bUseDesignParam = CONFIG.get(sQubit + ' Use Design Parameter')
		for sQubitParam in List_sQubitParam:
			sCallName = sQubit + ' ' + sQubitParam
			setattr(self, sQubitParam, CONFIG.get(sCallName))


class CapacitanceConfiguration():

	def __init__(self, CONFIG):
		for sCapParam in List_sCapParam:
			sCallName = 'Capacitance ' + sCapParam.replace('C', '')
			setattr(self, sCapParam, CONFIG.get(sCallName))
		self.r12 = self.C12 / np.sqrt(self.C1 * self.C2)
		self.r23 = self.C23 / np.sqrt(self.C2 * self.C3)
		self.r13 = self.r12 * self.r23 + self.C13 / np.sqrt(self.C1 * self.C3)


class simulation_3Q():

	def __init__(self, CONFIG):
		# init with some default settings
		self.nQubit = int(CONFIG.get('Number of Qubits')),
		self.nTrunc = int(CONFIG.get('Degree of Trunction'))
		self.dTimeStart = CONFIG.get('Time Start')
		self.dTimeEnd = CONFIG.get('Time End')
		self.dSampleFreq = CONFIG.get('Sampling Frequency')
		self.nTimeList = np.int(max((self.dTimeEnd - self.dTimeStart) * self.dSampleFreq + 1, 2))
		# self.nTimeList = int(CONFIG.get('Number of Times'))
		self.tlist = np.linspace(self.dTimeStart, self.dTimeEnd, self.nTimeList)
		self.dt = self.tlist[1] - self.tlist[0]
		# self.dSampleFreq_disp = CONFIG.get('Display Sampling Frequency')
		# self.nTimeList_disp = np.int((self.dTimeEnd - self.dTimeStart) * self.dSampleFreq_disp + 1)
		# self.tlist_disp = np.linspace(self.dTimeStart, self.dTimeEnd, self.nTimeList_disp)
		# self.dt_disp = self.tlist_disp[1] - self.tlist_disp[0]
		# self.nShow = 4

		# generate qubit idling config.
		for sQubit in List_sQubit:
			sName = 'qubitCfg_' + sQubit
			setattr(self, sName, QubitConfiguration(sQubit, CONFIG))
		# generate capacitance network config.
		self.capCfg = CapacitanceConfiguration(CONFIG)

		List_sLabel = [str(n) for n in range(16)]
		self.List_sLabel3 = []
		for k1 in np.arange(self.nTrunc):
			for k2 in np.arange(self.nTrunc):
				for k3 in np.arange(self.nTrunc):
					self.List_sLabel3.append(List_sLabel[k1] + List_sLabel[k2] + List_sLabel[k3])


		self.bUseSimpleState = CONFIG.get('Use Simple State')
		if self.bUseSimpleState:
			self.Q1_input = CONFIG.get('Q1 Input State')
			self.Q3_input = CONFIG.get('Q3 Input State')
			self.psi_input_logic = Qflatten(tensor(dict_psi[self.Q1_input], dict_psi[self.Q3_input]))
			self.rho_input_logic = self.psi_input_logic * self.psi_input_logic.dag()
		else:
			self.a00 = CONFIG.get('a00')
			self.a01 = CONFIG.get('a01')
			self.a10 = CONFIG.get('a10')
			self.a11 = CONFIG.get('a11')
			self.psi_input_logic = Qobj(np.array([self.a11,self.a10,self.a01,self.a00])).unit()
			self.rho_input_logic = self.psi_input_logic * self.psi_input_logic.dag()

		
		self.bUseT1Collapse = CONFIG.get('Use T1 Collapse')
		self.T1_Q1 = CONFIG.get('Q1 T1')
		self.T1_Q2 = CONFIG.get('Q2 T1')
		self.T1_Q3 = CONFIG.get('Q3 T1')
		self.c_ops = []


		### output quantities
		self.final_state = []
		self.final_pauli16 = []
		self.dict_Trace = {'Time Series: ' + key: [] for key in dict_pauli16.keys()}

		self.opts_mesolve = Options(atol=1e-10, rtol=1e-08, nsteps=10000)


	def updateSequence(self, sequence):
		# input sequence
		for sQubit in List_sQubit:
			for sSeqType in List_sSeqType:
				sName = 'seqCfg_' + sQubit + '_' + sSeqType
				setattr(self, sName, getattr(sequence, sName))


	def generateSubHamiltonian_3Q(self):
		# generate partial Hamiltonian in 3-qubit system
		OP = generateBasicOperator(self.nTrunc)
		self.OP = OP
		# self Hamiltonian operators
		self.H_Q1_aa = Qflatten(tensor(OP['aa'], OP['I'], OP['I']))
		self.H_Q1_aaaa = Qflatten(tensor(OP['aaaa'], OP['I'], OP['I']))
		self.H_Q2_aa = Qflatten(tensor(OP['I'], OP['aa'], OP['I']))
		self.H_Q2_aaaa = Qflatten(tensor(OP['I'], OP['aaaa'], OP['I']))
		self.H_Q3_aa = Qflatten(tensor(OP['I'], OP['I'], OP['aa']))
		self.H_Q3_aaaa = Qflatten(tensor(OP['I'], OP['I'], OP['aaaa']))
		# coupling Hamiltonian operators
		self.H_g12_xx = Qflatten(tensor(OP['x'], OP['x'], OP['I']))
		self.H_g23_xx = Qflatten(tensor(OP['I'], OP['x'], OP['x']))
		self.H_g13_xx = Qflatten(tensor(OP['x'], OP['I'], OP['x']))
		self.H_g12_pp = Qflatten(tensor(OP['p'], OP['p'], OP['I']))
		self.H_g23_pp = Qflatten(tensor(OP['I'], OP['p'], OP['p']))
		self.H_g13_pp = Qflatten(tensor(OP['p'], OP['I'], OP['p']))
		# drive Hamiltonian operators
		self.H_Q1_dr_x = Qflatten(tensor(OP['x'], OP['I'], OP['I']))
		self.H_Q2_dr_x = Qflatten(tensor(OP['I'], OP['x'], OP['I']))
		self.H_Q3_dr_x = Qflatten(tensor(OP['I'], OP['I'], OP['x']))
		self.H_Q1_dr_p = Qflatten(tensor(OP['p'], OP['I'], OP['I']))
		self.H_Q2_dr_p = Qflatten(tensor(OP['I'], OP['p'], OP['I']))
		self.H_Q3_dr_p = Qflatten(tensor(OP['I'], OP['I'], OP['p']))
		# collapse operators
		self.L_Q1_a = Qflatten(tensor(OP['a'], OP['I'], OP['I']))
		self.L_Q2_a = Qflatten(tensor(OP['I'], OP['a'], OP['I']))
		self.L_Q3_a = Qflatten(tensor(OP['I'], OP['I'], OP['a']))


	def generateHamiltonian_3Q_cap(self):
		# # construct 3-qubit Hamiltonian
		self.generateSubHamiltonian_3Q()
		# self Hamiltonian
		self.H_Q1 = self.qubitCfg_Q1.Frequency * self.H_Q1_aa + self.qubitCfg_Q1.Anharmonicity/2 * self.H_Q1_aaaa
		self.H_Q2 = self.qubitCfg_Q2.Frequency * self.H_Q2_aa + self.qubitCfg_Q2.Anharmonicity/2 * self.H_Q2_aaaa
		self.H_Q3 = self.qubitCfg_Q3.Frequency * self.H_Q3_aa + self.qubitCfg_Q3.Anharmonicity/2 * self.H_Q3_aaaa
		# coupling Hamiltonian
		self.g12_pp = 0.5 * self.capCfg.r12 * np.sqrt(self.qubitCfg_Q1.Frequency * self.qubitCfg_Q2.Frequency)
		self.H_12 = self.g12_pp * self.H_g12_pp
		self.g23_pp = 0.5 * self.capCfg.r23 * np.sqrt(self.qubitCfg_Q2.Frequency * self.qubitCfg_Q3.Frequency)
		self.H_23 = self.g23_pp * self.H_g23_pp
		self.g13_pp = 0.5 * self.capCfg.r13 * np.sqrt(self.qubitCfg_Q1.Frequency * self.qubitCfg_Q3.Frequency)
		self.H_13 = self.g13_pp * self.H_g13_pp
		# system Hamiltonian
		self.H_idle = self.H_Q1 + self.H_Q2 + self.H_Q3 + self.H_12 + self.H_23 + self.H_13
		# self.H_idle_2pi = 2*np.pi*self.H_idle


	def generateCollapse_3Q(self):
		self.Gamma1_Q1 = 1/self.T1_Q1
		self.Gamma1_Q2 = 1/self.T1_Q2
		self.Gamma1_Q3 = 1/self.T1_Q3
		self.c_ops = [np.sqrt(self.Gamma1_Q1) * self.L_Q1_a,
					 np.sqrt(self.Gamma1_Q2) * self.L_Q2_a,
					 np.sqrt(self.Gamma1_Q3) * self.L_Q3_a]


	def generateInitialState(self):
		#
		# self.generateLabel_3Q()
		self.list_label_sub = ['101','100','001','000']
		self.vals_idle, self.vecs_idle = eigensolve(self.H_idle)
		self.vals_idle_sub, self.vecs_idle_sub = level_identify(self.vals_idle, self.vecs_idle, self.List_sLabel3, self.list_label_sub)
		#
		self.H_idle_logic = Qobj(np.diag(self.vals_idle_sub))
		self.U_logic_to_full = Qobj(self.vecs_idle_sub)
		self.U_full_to_logic = self.U_logic_to_full.dag()
		#
		self.rho_input_logic_lab = T(self.rho_input_logic, U(2*np.pi*self.H_idle_logic, self.tlist[0]))
		self.rho_input_full_lab = T(self.rho_input_logic_lab, self.U_logic_to_full)
		self.rho0 = self.rho_input_full_lab
		#
		self.psi_input_logic_lab = U(2*np.pi*self.H_idle_logic, self.tlist[0]) * self.psi_input_logic
		self.psi_input_full_lab = self.U_logic_to_full * self.psi_input_logic_lab
		self.psi0 = self.psi_input_full_lab

		log.info(self.H_idle_logic)


	def rhoEvolver_3Q(self):
		#
		self.result_rho = mesolve(H=[
			[2*np.pi*self.H_Q1_aa, timeFunc_Q1_Frequency],
			[2*np.pi*self.H_Q1_aaaa, timeFunc_Q1_Anharmonicity],
			[2*np.pi*self.H_Q2_aa, timeFunc_Q2_Frequency],
			[2*np.pi*self.H_Q2_aaaa, timeFunc_Q2_Anharmonicity],
			[2*np.pi*self.H_Q3_aa, timeFunc_Q3_Frequency],
			[2*np.pi*self.H_Q3_aaaa, timeFunc_Q3_Anharmonicity],
			[2*np.pi*self.H_g12_pp, timeFunc_g12_pp],
			[2*np.pi*self.H_g23_pp, timeFunc_g23_pp],
			[2*np.pi*self.H_g13_pp, timeFunc_g13_pp],
			[2*np.pi*self.H_Q1_dr_p, timeFunc_Q1_DriveP],
			[2*np.pi*self.H_Q2_dr_p, timeFunc_Q2_DriveP],
			[2*np.pi*self.H_Q3_dr_p, timeFunc_Q3_DriveP]
			],
			rho0 = self.rho0, tlist = self.tlist, c_ops = self.c_ops, args = self)#, options = options), store_states=True, c_ops=[], e_ops=[]


	def psiEvolver_3Q(self):
		#
		self.result_psi = mesolve(H=[
			[2*np.pi*self.H_Q1_aa, timeFunc_Q1_Frequency],
			[2*np.pi*self.H_Q1_aaaa, timeFunc_Q1_Anharmonicity],
			[2*np.pi*self.H_Q2_aa, timeFunc_Q2_Frequency],
			[2*np.pi*self.H_Q2_aaaa, timeFunc_Q2_Anharmonicity],
			[2*np.pi*self.H_Q3_aa, timeFunc_Q3_Frequency],
			[2*np.pi*self.H_Q3_aaaa, timeFunc_Q3_Anharmonicity],
			[2*np.pi*self.H_g12_pp, timeFunc_g12_pp],
			[2*np.pi*self.H_g23_pp, timeFunc_g23_pp],
			[2*np.pi*self.H_g13_pp, timeFunc_g13_pp],
			[2*np.pi*self.H_Q1_dr_p, timeFunc_Q1_DriveP],
			[2*np.pi*self.H_Q2_dr_p, timeFunc_Q2_DriveP],
			[2*np.pi*self.H_Q3_dr_p, timeFunc_Q3_DriveP]
			],
			rho0 = self.psi0, tlist = self.tlist, c_ops = [], args = self, options=self.opts_mesolve)#, options = options), store_states=True, c_ops=[], e_ops=[]



	def generateFinalRho(self):
		rho_full_lab = self.result_rho.states[-1]
		rho_logic_lab = T(rho_full_lab, self.U_full_to_logic)
		rho_logic = T(rho_logic_lab, U(2*np.pi*self.H_idle_logic, self.tlist[-1]).dag())
		self.final_state = rho_logic.full().flatten()
		self.final_pauli16 = np.array([np.real((op * rho_logic).tr()) for op in dict_pauli16.values()])


	def generateTraceRho(self):
		for k, t in enumerate(self.tlist):
			rho_full_lab = self.result_rho.states[k]
			rho_logic_lab = T(rho_full_lab, self.U_full_to_logic)
			rho_logic = T(rho_logic_lab, U(2*np.pi*self.H_idle_logic, t).dag())
			for key, op in dict_pauli16.items():
				self.dict_Trace['Time Series: ' + key].append(np.real((op * rho_logic).tr()))


	def generateFinalPsi(self):
		psi_full_lab = self.result_psi.states[-1]
		psi_logic_lab = self.U_full_to_logic * psi_full_lab
		psi_logic = U(2*np.pi*self.H_idle_logic, self.tlist[-1]).dag() * psi_logic_lab
		self.final_state = psi_logic.full().T[0]
		self.final_pauli16 = np.array([np.real((op * psi_logic * psi_logic.dag()).tr()) for op in dict_pauli16.values()])


	def generateTracePsi(self):
		for k, t in enumerate(self.tlist):
			psi_full_lab = self.result_psi.states[k]
			psi_logic_lab = self.U_full_to_logic * psi_full_lab
			psi_logic = U(2*np.pi*self.H_idle_logic, t).dag() * psi_logic_lab
			for key, op in dict_pauli16.items():
				self.dict_Trace['Time Series: ' + key].append(np.real((op * psi_logic * psi_logic.dag()).tr()))