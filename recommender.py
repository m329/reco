from scipy.spatial import cKDTree
import numpy as np

class ArtistRecommender(object):

	def __init__(self):

		self.U = np.load('./all_U.npz')['arr_0']
		self.Umax = np.max(self.U,0)
		self.Umin = np.min(self.U,0)
		self.K = cKDTree(self.U)
		self.artist_list = np.load('./all_otherdata_list.npz')['arr_0']

	def getlocationof(self,artistId):
		inx = self.artist_list.tolist().index(artistId)
		searchpoint = self.U[ int(inx) ,: ]
		return searchpoint

	def maptobounds(self,x):
		"""
			assume x is in space from 0 to 1 and map this to the bounds
			of points in U
		"""
		return self.Umin+x*(self.Umax-self.Umin)

	def unmaptobounds(self,x):
		"""
			assume x is in the U space and map this to a space where points
			lie in [0,1] in every dimension
		"""
		return (x-self.Umin)/(self.Umax-self.Umin)

	def searchnear(self,searchpoint,k=5):

		[dist,inxes] = self.K.query(searchpoint,k=k)

		points = self.U[inxes,:]
		
		return [dist,self.artist_list[inxes],points]

	def recommend(self,artistId,k=5):

		inx = self.artist_list.tolist().index(artistId)
		searchpoint = self.U[ int(inx) ,: ]
		
		[dist,inxes] = self.K.query(searchpoint,k=k+1) # get the closest k+1 points since we're going to remove the searchpoint itself

		# find everything not equal to the search point in the results
		i=np.where(inxes!=inx)[0]

		# grab everything not at the position of the search point in the results
		inxes=inxes[i]
		dist=dist[i]
		points = self.U[inxes,:]
		
		return [dist,self.artist_list[inxes],points]
