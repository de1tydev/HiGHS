"""Small leakage/abstention guards, independent of the synthetic solver smoke."""
import copy,unittest
from history_start import propose
class HistoryTests(unittest.TestCase):
 def setUp(self):
  self.q=dict(start='2017-02-01T00:00:00Z',feature=[1,2],columns=['u0','u1'],topology='t')
  self.h=dict(id='a',end='2017-01-31T23:00:00Z',label_available='2017-01-31T23:30:00Z',feature=[1,2],columns=['u0','u1'],topology='t',u=[1,0],checked=True)
 def test_embargo_and_label_availability(self):
  for key in ('end','label_available'):
   h=dict(self.h,**{key:'2017-02-01T00:00:01Z'})
   self.assertEqual(propose(self.q,[h],'nearest')['suggestions'],{})
 def test_consensus_abstains_with_insufficient_or_conflicting_history(self):
  self.assertEqual(propose(self.q,[self.h],k=2)['suggestions'],{})
  self.assertEqual(propose(self.q,[self.h,dict(self.h,id='b',u=[1,1])],k=2)['suggestions'],{'u0':1})
 def test_incompatible_or_unchecked_excluded(self):
  for change in ({'topology':'different'},{'checked':False},{'columns':['u1','u0']}):
   self.assertEqual(propose(self.q,[dict(self.h,**change)],'nearest')['suggestions'],{})
 def test_invalid_labels_not_rounded(self):
  for u in ([1,0.00001],[True,0],[1,2]):
   with self.assertRaises(ValueError):propose(self.q,[dict(self.h,u=u)],'nearest')
 def test_no_input_mutation(self):
  orig=copy.deepcopy((self.q,self.h));propose(self.q,[self.h],'nearest');self.assertEqual((self.q,self.h),orig)
if __name__=='__main__':unittest.main()
