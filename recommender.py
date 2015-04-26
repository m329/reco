from scipy.spatial import cKDTree
import numpy as np

class ArtistRecommender(object):

	def __init__(self):

		self.U = np.load('./all_U.npz')['arr_0']
		
		# transform dimensions of U to be from 0 to 1
		
		self.Umax = np.max(self.U,0)
		self.Umin = np.min(self.U,0)
		self.Urange = self.Umax - self.Umin
		
		self.U = (self.U-self.Umin)/(self.Umax-self.Umin)
		
		# uncomment below for proportional transformation
		#self.U = (self.U-self.Umin)/np.max(self.Urange)
		
		self.Umax = np.max(self.U,0)
		self.Umin = np.min(self.U,0)
		self.Urange = self.Umax - self.Umin
				
		self.K = cKDTree(self.U)
		self.artist_list = np.load('./all_otherdata_list.npz')['arr_0']

	def getlocationof(self,artistId):
		inx = self.artist_list.tolist().index(artistId)
		searchpoint = self.U[ int(inx) ,: ]
		return searchpoint

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
