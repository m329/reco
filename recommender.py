from scipy.spatial import cKDTree
import numpy as np
import config

class ArtistRecommender(object):

	def __init__(self):

		self.U = np.load(config.U_path)['arr_0']
		
		# transform dimensions of U to be from 0 to 1
		
		# move outliers
		
		self.Umax = np.mean(self.U,0)+25*np.std(self.U,0)
		self.Umin = np.mean(self.U,0)-25*np.std(self.U,0)
		
		ndims=self.U.shape[1]
		
		for d in xrange(0,ndims):		
			self.U[ self.U[:,d]<self.Umin[d], d] = self.Umin[d]
			self.U[ self.U[:,d]>self.Umax[d], d] = self.Umax[d]
		
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
		self.artist_list = np.load(config.otherdata_path)['arr_0']

	def mapped(self,x,xmin=0,xmax=1):
		"""
			values come in as [0,1], map to U-space
		"""
		return self.Umin+x*self.Urange/(xmax-xmin)

	def unmapped(self,u,xmin=0,xmax=1):
		"""
			value is in U-space, map to [0,1]
		"""
		return xmin+u*(xmax-xmin)/self.Urange

	def getlocationof(self,artistId):
		inx = self.artist_list.tolist().index(artistId)
		searchpoint = self.U[ int(inx) ,: ]
		
		searchpoint = self.unmapped(searchpoint)
		
		return searchpoint

	def searchnear(self,searchpoint,k=5):

		searchpoint = self.mapped(searchpoint)

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
		
		points = [self.unmapped(p) for p in points]
		
		return [dist,self.artist_list[inxes],points]
